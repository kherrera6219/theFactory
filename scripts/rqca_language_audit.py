"""Positive + negative control for every live RQCA language.

Run this after touching `_LANGUAGE_RUNTIMES`. It is the check that unit tests
cannot make: whether each language's runtime actually accepts that language and
actually rejects something else.

    docker cp scripts/rqca_language_audit.py deploy-orchestrator-1:/tmp/  # or use
    # the shared sandbox workspace, whose path is already mounted:
    cp scripts/rqca_language_audit.py .sandbox-workspace/
    docker exec -e PYTHONPATH=/app deploy-orchestrator-1         python /sandbox-workspace/rqca_language_audit.py

Requires RQCA_AGENT_ENABLED=true and the sandbox workspace configured; see
docs/HANDOFF_CURRENT.md "RQCA / sandbox execution config". Pulls each language
image on first run, so budget time and disk.

Positive control: a hello-world in the language must PASS.
Negative control: a realistic Python-fallback artifact must NOT pass. That is
the failure mode this gate exists for -- a specialist that silently emits Python
under the target language's label. A language that passes the negative control
is worse than having no runtime at all, because it asserts a verification that
never happened. Two were found this way and neither was visible from the config:
PHP echoed a tagless file and exited 0, and TypeScript-on-node failed every
genuinely typed artifact.
"""
import asyncio
from types import SimpleNamespace

from orchestrator import rqca_agent

NL = chr(10)
Q = chr(34)

# A realistic Python fallback: what a specialist emits when it gives up on the
# target language but still labels the output as that language.
PY_FALLBACK = NL.join([
    "def word_count(path):",
    "    counts = {}",
    "    with open(path) as fh:",
    "        for line in fh:",
    "            for w in line.split():",
    "                counts[w] = counts.get(w, 0) + 1",
    "    return counts",
    "",
    "print(word_count(" + Q + "x.txt" + Q + "))",
    "",
])

GOOD = {
    "python":     ("main.py",    "print(" + Q + "hi" + Q + ")"),
    "javascript": ("main.js",    "console.log(" + Q + "hi" + Q + ");"),
    "typescript": ("main.ts",    "const m: string = " + Q + "hi" + Q + "; console.log(m);"),
    "ruby":       ("main.rb",    "puts " + Q + "hi" + Q),
    "php":        ("main.php",   "<?php echo " + Q + "hi" + Q + ";"),
    "r":          ("main.R",     "cat(" + Q + "hi" + Q + ")"),
    "julia":      ("main.jl",    "println(" + Q + "hi" + Q + ")"),
    "ocaml":      ("main.ml",    "let () = print_endline " + Q + "hi" + Q),
    "c":          ("main.c",     NL.join(["#include <stdio.h>", "int main(void){ puts(" + Q + "hi" + Q + "); return 0; }"])),
    "cpp":        ("main.cpp",   NL.join(["#include <cstdio>", "int main(){ puts(" + Q + "hi" + Q + "); return 0; }"])),
    "rust":       ("main.rs",    "fn main(){ println!(" + Q + "hi" + Q + "); }"),
    "go":         ("main.go",    NL.join(["package main", "import " + Q + "fmt" + Q, "func main(){ fmt.Println(" + Q + "hi" + Q + ") }"])),
    "zig":        ("main.zig",   NL.join(["const std = @import(" + Q + "std" + Q + ");",
                                          "pub fn main() !void { try std.io.getStdOut().writer().print(" + Q + "hi" + Q + ", .{}); }"])),
    "haskell":    ("main.hs",    NL.join(["main :: IO ()", "main = putStrLn " + Q + "hi" + Q])),
    "java":       ("Main.java",  "public class Main { public static void main(String[] a){ System.out.println(" + Q + "hi" + Q + "); } }"),
    "kotlin":     ("main.kt",    "fun main(){ println(" + Q + "hi" + Q + ") }"),
    "scala":      ("Main.scala", "object Main { def main(a: Array[String]): Unit = println(" + Q + "hi" + Q + ") }"),
    "matlab":     ("main.m",     "disp('hi')"),
    "mathematica":("main.wl",    "Print[" + Q + "hi" + Q + "]"),
}


def run(lang, filename, code):
    return asyncio.run(rqca_agent.run_runtime_qc(
        mission_id="audit-" + lang,
        generated_output={"filename": filename, "generated_code": code + NL, "language": lang},
        testdata_manifest={}, integration_tests=None, language=lang,
        settings=SimpleNamespace(docker_bin="docker")))


holes = []
print("%-13s %-8s %-9s %s" % ("LANGUAGE", "HELLO", "PY-FAKE", "NOTES"))
for lang in sorted(GOOD):
    filename, code = GOOD[lang]
    good = run(lang, filename, code)
    bad = run(lang, filename, PY_FALLBACK)
    good_v, bad_v = good.get("verdict"), bad.get("verdict")
    notes = []
    sub = good.get("runtime_substitute")
    if sub:
        notes.append("via " + sub + " (" + str(good.get("verified_scope")) + ")")
    if bad.get("failed_on_pattern"):
        notes.append("caught by pattern " + repr(bad["failed_on_pattern"]))
    if bad_v == "PASS":
        holes.append(lang)
        notes.append("*** FALSE PASS: Python accepted as " + lang + " ***")
    print("%-13s %-8s %-9s %s" % (lang, good_v, bad_v, "; ".join(notes)))

print()
print("languages where Python source falsely PASSES:", holes or "none")
