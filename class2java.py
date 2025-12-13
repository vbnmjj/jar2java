import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

CFR = "cfr-0.152.jar"

def decompile_jar(jar_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cmd = [
        "java", "-jar", CFR,
        jar_path,
        "--outputdir", out_dir
    ]

    print("Running:", " ".join(cmd))
    subprocess.run(cmd)

def main(jar_dir, out_root):
    jars = [os.path.join(jar_dir, f) for f in os.listdir(jar_dir) if f.endswith(".jar")]
    print(f"Found {len(jars)} jars in {jar_dir}")
    with ThreadPoolExecutor(max_workers=5) as pool:
        for jar in jars:
            name = os.path.basename(jar).replace(".jar", "")
            pool.submit(decompile_jar, jar, os.path.join(out_root, name))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
