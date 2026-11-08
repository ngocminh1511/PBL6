"""Explicit R2 sync; uploads happen only when the CLI is called with --upload."""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .catalog import PROCESSED_DIR, RAW_DIR, load_manifest, local_path, now, read_json, relative, sha256, write_json
from .object_storage import R2Store, error_code


def inventory(raw_dir=RAW_DIR, output_dir=PROCESSED_DIR) -> list[dict]:
    raw=load_manifest(raw_dir)
    result=[]
    for artifact_id,a in raw["artifacts"].items():
        if artifact_id!="sha256:"+a["sha256"]:
            raise ValueError("Artifact identity differs from its checksum")
        result.append({"id":artifact_id,"namespace":"artifacts","sha256":a["sha256"],"path":a["path"],"file_name":a["file_name"]})
    for path in sorted((output_dir/"normalized").glob("*.html")):
        result.append({"id":path.stem,"namespace":"normalized","sha256":sha256(path.read_bytes()),"path":relative(path),"file_name":path.name})
    return result


def publish_locations(report, raw_dir=RAW_DIR, output_dir=PROCESSED_DIR):
    """Persist only verified locations, retaining every local path and every source relation."""
    manifest=load_manifest(raw_dir)
    for entry in report["objects"].values():
        if entry["namespace"]=="artifacts" and entry["id"] in manifest["artifacts"]:
            artifact=manifest["artifacts"][entry["id"]]
            if artifact["sha256"]!=entry["sha256"]:
                raise ValueError("Manifest changed during sync")
            artifact.update(storage_backend="r2",r2=entry["r2"])
    for document in manifest["documents"].values():
        for file in document.get("files",[]):
            source=manifest["artifacts"].get(file["artifact_id"],{})
            if source.get("r2"):
                file.update(storage_backend="r2",r2=source["r2"])
    count=sum(a.get("storage_backend")=="r2" for a in manifest["artifacts"].values())
    manifest["storage_backend"]="r2" if count==len(manifest["artifacts"]) and count else "mixed" if count else "local"
    manifest["updated_at"]=now()
    write_json(raw_dir/"manifest.json",manifest)
    write_json(output_dir/"artifacts.json",manifest["artifacts"])
    if (raw_dir/"collection_manifest.json").is_file():
        write_json(raw_dir/"collection_manifest.json",manifest)
    processed=read_json(output_dir/"manifest.json",{})
    if processed:
        processed["storage_backend"]=manifest["storage_backend"]
        write_json(output_dir/"manifest.json",processed)


def run(*, upload=False, limit=None, store=None, raw_dir=RAW_DIR, output_dir=PROCESSED_DIR, progress=print):
    store=store or R2Store()
    report_path=output_dir/"r2_sync_report.json"
    try:
        store.check_bucket()
        jobs=inventory(raw_dir,output_dir)
        summary={"checked_at":now(),"bucket":store.config.bucket,"prefix":store.config.prefix,
                 "source_files":sum(j["namespace"]=="artifacts" for j in jobs),"normalized_files":sum(j["namespace"]=="normalized" for j in jobs)}
        write_json(output_dir/"r2_connection_report.json",{**summary,"status":"connected","write_access":"not_probed","upload_started":upload})
        if not upload:
            return {**summary,"status":"checked","upload_started":False}
        previous=read_json(report_path,{})
        previous_objects={key:value for key,value in previous.get("objects",{}).items()
                          if value.get("r2",{}).get("bucket")==store.config.bucket
                          and value.get("r2",{}).get("key","").startswith(store.config.prefix+"/")}
        report={**summary,"status":"running","objects":previous_objects,"errors":[],"local_backups_retained":True,"automatic_upload":False}
        # Preserve the exact pre-sync storage metadata for recovery; do not overwrite on resume.
        backup=raw_dir/"manifest.before_r2.json"
        if not backup.exists():
            write_json(backup,load_manifest(raw_dir))
        if limit:
            jobs=jobs[:limit]
        # Hash-identical normalized files share a physical object; all logical file relations remain.
        groups={}
        for job in jobs:
            groups.setdefault((job["namespace"],job["sha256"]),[]).append(job)
        uploaded=reused=0
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending={pool.submit(store.upload_verified,local_path(group[0]["path"]),group[0]["sha256"],filename=group[0]["file_name"],namespace=group[0]["namespace"]):group for group in groups.values()}
            for future in as_completed(pending):
                group=pending[future]
                try:
                    record=future.result()
                    uploaded+=record["status"]=="uploaded"
                    reused+=record["status"]=="already_present"
                    for job in group:
                        report["objects"][job["namespace"]+":"+job["id"]]={**job,"r2":record}
                except Exception as exc:
                    report["errors"].append({"id":group[0]["id"],"namespace":group[0]["namespace"],"error_type":type(exc).__name__,"error_code":error_code(exc)})
                report.update(updated_at=now(),uploaded_this_run=uploaded,reused_this_run=reused)
                write_json(report_path,report)
                if progress and (len(report["objects"])%20==0 or report["errors"]):
                    progress(f"R2: {len(report['objects'])} verified file locations; {len(report['errors'])} errors",flush=True)
        expected={j["namespace"]+":"+j["id"] for j in inventory(raw_dir,output_dir)}
        complete=not report["errors"] and expected<=report["objects"].keys()
        report.update(status="synced" if complete else "partial",completed_at=now(),
                      verified_file_locations=len(expected & report["objects"].keys()),
                      verified_bytes=sum(j["r2"]["bytes"] for key,j in report["objects"].items() if key in expected))
        publish_locations(report,raw_dir,output_dir)
        write_json(report_path,report)
        write_json(output_dir/"r2_connection_report.json",{**summary,"status":"connected","write_access":"verified" if uploaded or reused else "failed","upload_started":True})
        return {k:v for k,v in report.items() if k!="objects"}
    except Exception as exc:
        failure={"checked_at":now(),"status":"failed","error_type":type(exc).__name__,"error_code":error_code(exc)}
        write_json(output_dir/"r2_connection_report.json",failure)
        return failure
    finally:
        store.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload",action="store_true",help="Explicitly upload and activate verified R2 locations")
    parser.add_argument("--limit",type=int,help="First N file locations for a sample upload")
    args=parser.parse_args()
    if args.limit is not None and args.limit<1:
        parser.error("--limit must be positive")
    result=run(upload=args.upload,limit=args.limit)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result["status"] in {"failed","partial"} and not args.limit:
        raise SystemExit(1)


if __name__=="__main__":
    main()
