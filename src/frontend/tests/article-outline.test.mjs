import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/articleOutline.ts', import.meta.url), 'utf8');
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const context = { exports: {} };
runInNewContext(output, context);
const { articleLines, articleTitle, countLevels, outlineItems, pathTo, foldText } = context.exports;

const dieu = (id, number, doc, text = '', children = []) =>
  ({ id, type: 'Dieu', title: `Tên ${number} (${doc})`, article_number: number, document_number: doc, text, children });

const tree = {
  id: '20.2', type: 'DeMuc', title: 'Đề mục 20.2', children: [
    { id: 'c1', type: 'Chuong', title: 'Chương I', children: [
      dieu('a1', '1', '45/2019/QH14'), dieu('a2', '2', '45/2019/QH14'), dieu('b1', '1', '135/2020/NĐ-CP'),
    ] },
  ],
};

test('articles of a chapter are grouped by consecutive source document', () => {
  const groups = outlineItems(tree.children[0]);
  assert.deepEqual(JSON.parse(JSON.stringify(groups.map((g) => [g.source, g.articles.map((a) => a.id)]))),
    [['45/2019/QH14', ['a1', 'a2']], ['135/2020/NĐ-CP', ['b1']]]);
  assert.equal(articleTitle(tree.children[0].children[0]), 'Tên 1');
  assert.deepEqual([...pathTo(tree, 'b1')], ['c1']);
  assert.equal(countLevels(tree).chuong, 1);
  assert.equal(countLevels(tree).dieu, 3);
  assert.equal(foldText('Điều Quyền'), 'dieu quyen');
});

test('Phap dien text is read once even though its clauses repeat it', () => {
  const text = '1. Người lao động có các quyền:\r\na) Làm việc;\r\n2. Nghĩa vụ.';
  const lines = articleLines(dieu('x', '5', 'd', text, [
    { id: 'k1', type: 'SourceComponent', clause_number: '1', text: '1. Người lao động có các quyền:\na) Làm việc;' },
    { id: 'k2', type: 'SourceComponent', clause_number: '2', text: '2. Nghĩa vụ.' },
  ]));
  assert.deepEqual(JSON.parse(JSON.stringify(lines)), [
    { kind: 'clause', label: '1.', text: 'Người lao động có các quyền:' },
    { kind: 'point', label: 'a)', text: 'Làm việc;' },
    { kind: 'clause', label: '2.', text: 'Nghĩa vụ.' },
  ]);
});

test('PDF clauses and points without numbers in their text get them from the tree', () => {
  const article = { id: 'p', type: 'article', title: 'Phạm vi', article_number: '1', text: 'Mở đầu.', children: [
    { id: 'k', type: 'clause', clause_number: '1', text: 'Khoản một.', children: [
      { id: 'd', type: 'point', point_number: 'a', text: 'Điểm a.' }] },
  ] };
  assert.deepEqual(JSON.parse(JSON.stringify(articleLines(article))), [
    { kind: 'text', text: 'Mở đầu.' },
    { kind: 'clause', label: '1.', text: 'Khoản một.' },
    { kind: 'point', label: 'a)', text: 'Điểm a.' },
  ]);
});
