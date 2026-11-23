"""Named LLM connections. Secrets stay encrypted and activation is transactional."""
from copy import deepcopy
from uuid import uuid4
from labor_rag.llm_providers import CLOUD_API_PROVIDERS, base_url_field, model_field, secret_field

from fastapi import HTTPException
from .configuration import GROUP_FIELDS, cipher

PROVIDERS = {"gemini", "openai", "anthropic", "local"} | CLOUD_API_PROVIDERS


def profile_from_settings(settings, *, identity="environment", source="environment", name="Từ môi trường"):
    provider = settings.LLM_PROVIDER
    return {"id": identity, "name": name, "mode": "local" if provider == "local" else "cloud",
            "provider": provider, "model": getattr(settings, model_field(provider).upper()),
            "base_url": getattr(settings, base_url_field(provider).upper()) if base_url_field(provider) else "", "local_runtime": "compatible",
            "api_key_source": source, "api_key": getattr(settings, secret_field(provider).upper()) if source == "custom" else None,
            "reasoning": settings.LLM_REASONING, "verification": None}


def encode_profiles(profiles, key):
    result = []
    for profile in profiles:
        item = {k: v for k, v in profile.items() if k != "api_key"}
        if profile.get("api_key_source") == "custom" and profile.get("api_key"):
            item["encrypted_api_key"] = cipher(key).encrypt(profile["api_key"].encode()).decode()
        result.append(item)
    return result


def decode_profiles(profiles, key):
    result = []
    for profile in profiles:
        item = dict(profile)
        encrypted = item.pop("encrypted_api_key", None)
        if encrypted:
            try:
                item["api_key"] = cipher(key).decrypt(encrypted.encode()).decode()
            except Exception:
                raise ValueError("Không giải mã được API key của cấu hình LLM.") from None
        result.append(item)
    return result


class LLMProfiles:
    def __init__(self, runtime):
        self.runtime = runtime

    def find(self, identity):
        if identity == "environment":
            return profile_from_settings(self.runtime.base)
        profile = next((p for p in self.runtime.llm_profiles if p["id"] == identity), None)
        if not profile:
            raise HTTPException(404, "Không tìm thấy cấu hình LLM.")
        return profile

    def key(self, profile):
        if profile["api_key_source"] == "environment":
            return getattr(self.runtime.base, secret_field(profile["provider"]).upper())
        return profile.get("api_key") or ""

    def public(self, profile):
        return {"reasoning": "default"} | {k: v for k, v in profile.items() if k not in {"api_key", "encrypted_api_key"}} | {
            "key_configured": bool(self.key(profile)), "read_only": profile["id"] == "environment"}

    def listing(self):
        with self.runtime.lock:
            config = self.runtime.config()
            return {"profiles": [self.public(profile_from_settings(self.runtime.base))] +
                    [self.public(profile) for profile in self.runtime.llm_profiles],
                    "active_profile_id": self.runtime.active_llm_profile_id or "environment",
                    "config_version": self.runtime.version, "can_save": config["can_save"],
                    "encryption_ready": config["encryption_ready"]}

    def draft(self, body, identity=None):
        data = body.model_dump(exclude={"config_version", "activate", "profile_id", "copy_key_from"})
        if (data["mode"] == "local") != (data["provider"] == "local"):
            raise HTTPException(422, "Chọn Local/Cloud trước, rồi chọn nhà cung cấp phù hợp.")
        if data["provider"] not in PROVIDERS:
            raise HTTPException(422, "Nhà cung cấp chưa được hỗ trợ.")
        if data["api_key_source"] == "none" and data["mode"] != "local":
            raise HTTPException(422, "Kết nối cloud cần API key.")
        data["name"], data["model"] = data["name"].strip(), data["model"].strip()
        endpoint_field = base_url_field(data["provider"])
        data["base_url"] = data["base_url"].strip() if endpoint_field else ""
        if data["provider"] in CLOUD_API_PROVIDERS and not data["base_url"]:
            data["base_url"] = getattr(self.runtime.base, endpoint_field.upper())
        if endpoint_field and not data["base_url"]:
            raise HTTPException(422, "Nhập địa chỉ API (Base URL) của nhà cung cấp đã chọn.")
        # A duplicate may reuse its source's stored key without sending it to the browser.
        key_owner = identity or body.copy_key_from
        existing = self.find(key_owner) if key_owner and key_owner != "environment" else None
        if data["api_key_source"] == "custom" and not data["api_key"]:
            data["api_key"] = existing.get("api_key") if existing and existing["provider"] == data["provider"] else None
        if data["api_key_source"] != "custom":
            data["api_key"] = None
        data.update(id=identity or uuid4().hex, verification=None)
        return data

    def settings(self, profile):
        values = {k: v for k, v in self.runtime.overrides.items() if k not in GROUP_FIELDS["llm"]}
        if profile["id"] == "environment":
            return self.runtime.make_settings(values), values
        provider = profile["provider"]
        # Profiles saved before reasoning levels existed keep the model default.
        values.update(llm_provider=provider, llm_reasoning=profile.get("reasoning") or "default")
        values[model_field(provider)] = profile["model"]
        # An environment-backed profile inherits only its provider's startup key.
        if profile["api_key_source"] != "environment":
            values[secret_field(provider)] = self.key(profile)
        endpoint_field = base_url_field(provider)
        if endpoint_field:
            values[endpoint_field] = profile["base_url"]
        try:
            return self.runtime.make_settings(values), values
        except ValueError:
            raise HTTPException(422, "Endpoint hoặc cấu hình LLM chưa hợp lệ.") from None

    def check(self, body):
        with self.runtime.lock:
            self.runtime.ensure_ready()
            profile = self.draft(body, body.profile_id)
            settings, _ = self.settings(profile)
        return self.runtime.check_group("llm", settings)

    def models(self, body):
        with self.runtime.lock:
            self.runtime.ensure_ready()
            profile = self.draft(body, body.profile_id)
            settings, _ = self.settings(profile)
        return self.runtime.list_models(settings)

    def mutate(self, action, *, body=None, identity=None, expected_version=None):
        runtime = self.runtime
        if not runtime.lock.acquire(blocking=False):
            raise HTTPException(409, "Đang xử lý tác vụ; thử lại sau.")
        try:
            runtime.check_write(expected_version)
            profiles = deepcopy(runtime.llm_profiles)
            active_id = runtime.active_llm_profile_id
            candidate, values = runtime.settings, dict(runtime.overrides)
            if action == "delete":
                self.find(identity)
                if identity == "environment" or identity == active_id:
                    raise HTTPException(409, "Chọn cấu hình khác trước khi xóa cấu hình đang sử dụng.")
                profiles = [p for p in profiles if p["id"] != identity]
            else:
                if action == "activate":
                    profile = deepcopy(self.find(identity))
                else:
                    if identity == "environment":
                        raise HTTPException(422, "Dùng Thêm cấu hình để tạo kết nối riêng từ cấu hình môi trường.")
                    profile = self.draft(body, identity)
                    if not profile["name"] or not profile["model"]:
                        raise HTTPException(422, "Cần tên cấu hình và model.")
                    # Validate encryption availability before making an API request.
                    encode_profiles([profile], runtime.base.CONFIG_ENCRYPTION_KEY)
                checked_settings, checked_values = self.settings(profile)
                verification = runtime.check_group("llm", checked_settings)
                if verification["status"] != "passed":
                    raise HTTPException(503, verification["message"])
                profile["verification"] = verification
                if profile["id"] != "environment":
                    profiles = [p for p in profiles if p["id"] != profile["id"]] + [profile]
                if action == "activate" or (body and body.activate) or profile["id"] == active_id:
                    candidate, values = checked_settings, checked_values
                    active_id = None if profile["id"] == "environment" else profile["id"]
            runtime.commit_configuration(candidate, values, profiles=profiles, active_profile_id=active_id)
            return self.listing()
        except ValueError:
            raise HTTPException(422, "Cần CONFIG_ENCRYPTION_KEY hợp lệ để lưu API key riêng.") from None
        finally:
            runtime.lock.release()
