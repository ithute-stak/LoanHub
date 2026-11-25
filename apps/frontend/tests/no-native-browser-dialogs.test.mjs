/* Reject native browser alert/confirm/prompt calls in all LoanHub frontend source. */
import assert from "node:assert/strict";
import {readdirSync, readFileSync} from "node:fs";
import {join, relative, resolve} from "node:path";
import {test} from "node:test";
import ts from "typescript";

const ROOT = resolve(import.meta.dirname, "..");
const DIRECTORIES = ["api", "app", "components", "hooks", "lib", "provider", "store", "utils"];
const EXTS = /\.(?:ts|tsx|js|jsx|mjs)$/;
const NATIVE = new Set(["alert", "confirm", "prompt"]);
const ROOT_OBJECTS = new Set(["window", "globalThis", "self"]);

function walk(directory) {
    return readdirSync(directory, {withFileTypes: true}).flatMap((item) => {
        const path = join(directory, item.name);
        if (item.isDirectory()) return walk(path);
        return item.isFile() && EXTS.test(item.name) ? [path] : [];
    });
}

function nativeInvocation(node) {
    if (ts.isIdentifier(node)) return NATIVE.has(node.text) ? node.text : null;
    if (ts.isPropertyAccessExpression(node)
        && ts.isIdentifier(node.expression)
        && ROOT_OBJECTS.has(node.expression.text)
        && NATIVE.has(node.name.text)) return node.name.text;
    if (ts.isElementAccessExpression(node)
        && ts.isIdentifier(node.expression)
        && ROOT_OBJECTS.has(node.expression.text)
        && ts.isStringLiteral(node.argumentExpression)
        && NATIVE.has(node.argumentExpression.text)) return node.argumentExpression.text;
    return null;
}

test("LoanHub frontend never invokes default browser alert, confirm, or prompt dialogs", () => {
    const violations = [];
    let scanned = 0;
    for (const directory of DIRECTORIES) {
        for (const file of walk(join(ROOT, directory))) {
            const source = readFileSync(file, "utf8");
            const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true,
                file.endsWith(".tsx") || file.endsWith(".jsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
            scanned++;
            function visit(node) {
                if (ts.isCallExpression(node)) {
                    const native = nativeInvocation(node.expression);
                    if (native) {
                        const pos = tree.getLineAndCharacterOfPosition(node.getStart(tree));
                        violations.push(`${relative(ROOT, file)}:${pos.line + 1} native ${native}()`);
                    }
                }
                ts.forEachChild(node, visit);
            }
            visit(tree);
        }
    }
    assert.ok(scanned > 400, `Expected the full frontend source tree; scanned ${scanned} files`);
    assert.deepEqual(violations, [], `Native browser dialogs must use LoanHub's branded UI:\n${violations.join("\n")}`);
});
