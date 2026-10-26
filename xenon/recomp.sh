#!/bin/sh
# Regenerate xenon/ppc with XenonRecomp, using rex_context.h so the output
# builds against the ReXGlue runtime (game: -DFIFA08_USE_XENONRECOMP=ON).
# Output goes to ppc.new first; only changed files are copied into ppc (so the
# game build recompiles just those), and files left from an earlier, bigger
# run are deleted.
cd "$(dirname "$0")"
rm -rf ppc.new
mkdir -p ppc ppc.new
cat fifa08_switch_tables.toml manual_switch_tables.toml > switch_tables.new.toml
sed 's|^out_directory_path = "ppc"|out_directory_path = "ppc.new"|; s|^switch_table_file_path = "fifa08_switch_tables.toml"|switch_table_file_path = "switch_tables.new.toml"|' fifa08.toml > fifa08.new.toml
../third_party/XenonRecomp/build/XenonRecomp/XenonRecomp.exe fifa08.new.toml rex_context.h > ../out-xenon-recomp.txt 2>&1
rm -f fifa08.new.toml switch_tables.new.toml
changed=0
for f in ppc.new/*; do
    n=ppc/$(basename "$f")
    if ! cmp -s "$f" "$n"; then cp "$f" "$n"; changed=$((changed + 1)); fi
done
for f in ppc/*; do
    [ -e "ppc.new/$(basename "$f")" ] || { rm -f "$f"; echo "removed stale $f"; }
done
rm -rf ppc.new
echo "$changed files changed"
grep -v "Recompiling" ../out-xenon-recomp.txt | sed -E 's/ at [0-9A-F]+//; s/instruction [0-9A-F]+/instruction X/; s/ [0-9A-F]{8}(,|$)/ X\1/g' | sort | uniq -c
