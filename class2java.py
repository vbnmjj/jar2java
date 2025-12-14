import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

CFR = "cfr-0.152.jar"
MAX_WORKERS = 5


def run_cfr(target_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cmd = [
        "java", "-jar", CFR,
        target_path,
        "--outputdir", out_dir
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def collect_targets(root_dir):
    jars = []
    classes = []

    for root, _, files in os.walk(root_dir):
        for f in files:
            full = os.path.join(root, f)
            if f.endswith(".jar"):
                jars.append(full)
            elif f.endswith(".class"):
                classes.append(full)

    return jars, classes


def main(input_dir, out_root):
    jars, classes = collect_targets(input_dir)

    print(f"[+] Found {len(jars)} jar files")
    print(f"[+] Found {len(classes)} class files")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        # 处理 jar
        for jar in jars:
            name = os.path.basename(jar).replace(".jar", "")
            pool.submit(
                run_cfr,
                jar,
                os.path.join(out_root, "jar", name)
            )

        # 处理 class
        # class 统一输出到 class 目录，由 CFR 自己还原包结构
        class_out = os.path.join(out_root, "class")
        for cls in classes:
            pool.submit(
                run_cfr,
                cls,
                class_out
            )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python class2java.py <input_dir> <output_dir>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
