// Run: node --experimental-strip-types --test tests/stackTables.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { cellLabels } from "../src/stackTables.ts";

test("each cell gets the header of its column", () => {
  assert.deepEqual(cellLabels(["Nama", "Email", "Status", "Aksi"], [1, 1, 1, 1]), ["Nama", "Email", "Status", "Aksi"]);
});

test("colspan: a wide cell (empty state) has no label, later cells keep their own column", () => {
  assert.deepEqual(cellLabels(["Nama", "Email", "Status"], [3]), [null]);
  assert.deepEqual(cellLabels(["A", "B", "C", "D"], [1, 2, 1]), ["A", null, "D"]);
});

test("blank header (e.g. an icon-only action column) gives no label", () => {
  assert.deepEqual(cellLabels(["Nama", " "], [1, 1]), ["Nama", null]);
  assert.deepEqual(cellLabels(["Nama"], [1, 1]), ["Nama", null]);          // more cells than headers
});
