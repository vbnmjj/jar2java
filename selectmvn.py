import os
import re
import zipfile
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import argparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 全局锁
print_lock = threading.Lock()

# Maven Central API
MAVEN_CENTRAL_API = "https://search.maven.org/solrsearch/select?q=a:{0}+AND+v:{1}&rows=50&wt=json"
MAVEN_CENTRAL_POM = "https://repo1.maven.org/maven2/{0}/{1}/{2}/{1}-{2}.pom"

# 配置
THREAD_NUM = 60
REQUEST_TIMEOUT = 30
MAX_RETRIES = 2

# 参数解析
parser = argparse.ArgumentParser(description="JAR 智能分类工具")
parser.add_argument("-o", "--output", help="将私有库解压到该目录", required=False)
args = parser.parse_args()

# 线程局部 Session
thread_local = threading.local()

# 黑名单公共库前缀
KNOWN_PUBLIC_PREFIXES = {
    'spring-', 'commons-', 'slf4j-', 'log4j-', 'logback-',
    'junit-', 'hamcrest-', 'jmock-', 'objenesis-',
    'javax.', 'activation-', 'lombok-', 'aspectjweaver-',
    'cglib-', 'asm-', 'javassist-', 'mysql-', 'postgresql-',
    'ojdbc', 'sqljdbc', 'jtds-', 'sqlitejdbc-', 'hibernate-',
    'mybatis-', 'jackson-', 'gson-', 'fastjson-', 'json-lib',
    'json-20', 'json_simple', 'dom4j-', 'jdom-', 'xom-',
    'xmlbeans-', 'xercesImpl-', 'xml-apis', 'stax-', 'jaxb-',
    'jaxen-', 'xalan-', 'xmlsec-', 'xmlgraphics-', 'okhttp-',
    'retrofit-', 'netty-', 'httpclient-', 'guava-', 'caffeine-',
    'reactor-', 'reactive-streams-', 'poi-', 'itext-', 'jodconverter',
    'ooxml-schemas-', 'freemarker-', 'velocity-', 'thymeleaf-',
    'joda-time-', 'servlet-api', 'jsp-api', 'jstl-', 'standard-',
    'mail-', 'saaj-', 'axis-', 'wsdl4j-', 'wss4j-', 'opensaml-',
    'jaxrpc-', 'jaxws-', 'ant-', 'bcel-', 'oro-', 'regexp-',
    'jfreechart-', 'jcommon-', 'batik-', 'fop-', 'jai_', 'sac-',
    'kaptcha-', 'lucene-', 'elasticsearch-', 'solr-', 'bcprov-',
    'bcmail-', 'bctsp-', 'xapool-', 'c3p0-', 'druid-', 'hikaricp-',
    'ognl-', 'qdox-', 'antlr-', 'icu4j-', 'xpp3', 'htmlparser-',
    'jsoup-', 'jibx-', 'XmlSchema-', 'FastInfoset-', 'wstx-',
    'tribes-', 'sigar-', 'clojure-', 'jalopy-', 'je-', 'jurt-',
    'ridl-', 'unoil-', 'juh-', 'xml-resolver-', 'aopalliance-',
    'xfire-', 'jasperreports-', 'wmf2svg-', 'taobao-','jftp-','sm3diges',
    'jotm-','jaas-','jxl','xmpush-','jacob-','jspsmart-','QRCode'
}

# 白名单前缀
PRIVATE_PREFIXES = {}

def get_session():
    if not hasattr(thread_local, "session"):
        session = requests.Session()
        retry_strategy = Retry(
            total=3, backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET"]
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )
        session.mount("https://", adapter)
        thread_local.session = session
    return thread_local.session


def extract_jar_name_info(jar_path):
    filename = os.path.basename(jar_path)
    name_without_ext = filename[:-4] if filename.endswith('.jar') else filename
    match = re.match(r'^(.+?)[-_](\d+[\d\.\-_A-Za-z]*)$', name_without_ext)
    if match:
        return match.group(1), match.group(2)
    return name_without_ext, None


def is_known_public_library(jar_name):
    jar_lower = jar_name.lower()
    return any(jar_lower.startswith(prefix.lower()) for prefix in KNOWN_PUBLIC_PREFIXES)


def is_private_library(jar_name):
    jar_lower = jar_name.lower()
    return any(prefix.lower() in jar_lower for prefix in PRIVATE_PREFIXES)


def extract_maven_coords(jar_path):
    if not os.path.exists(jar_path) or not zipfile.is_zipfile(jar_path):
        return None

    try:
        with zipfile.ZipFile(jar_path, 'r') as zf:
            pom_prop_paths = [f for f in zf.namelist()
                            if f.endswith("pom.properties") and "META-INF/maven/" in f]
            if not pom_prop_paths:
                return None

            with zf.open(pom_prop_paths[0]) as f:
                content = f.read().decode('utf-8', errors='ignore')

            group_id = re.search(r"groupId\s*=\s*(.+?)\s*$", content, re.MULTILINE)
            artifact_id = re.search(r"artifactId\s*=\s*(.+?)\s*$", content, re.MULTILINE)
            version = re.search(r"version\s*=\s*(.+?)\s*$", content, re.MULTILINE)

            if group_id and artifact_id and version:
                return (
                    group_id.group(1).strip(),
                    artifact_id.group(1).strip(),
                    version.group(1).strip()
                )
    except Exception as e:
        with print_lock:
            print(f"[ERROR] 解析失败: {os.path.basename(jar_path)} - {str(e)}")
    return None


def verify_by_artifact_version(artifact_id, version):
    session = get_session()
    try:
        url = MAVEN_CENTRAL_API.format(artifact_id, version)
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return data.get("response", {}).get("numFound", 0) > 0
    except Exception:
        return False


def verify_via_pom_url(group_id, artifact_id, version):
    try:
        group_path = group_id.replace('.', '/')
        pom_url = MAVEN_CENTRAL_POM.format(group_path, artifact_id, version)
        session = get_session()
        response = session.head(pom_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        return response.status_code == 200
    except Exception:
        return False


def classify_single_jar(jar_path, index, total):
    jar_name = os.path.basename(jar_path)
    with print_lock:
        print(f"[{index}/{total}] {jar_name}")

    if is_private_library(jar_name):
        with print_lock:
            print(f"  └─ ❌ 私人包(公司私有库)")
        return ("private", jar_path, "company_library")

    if is_known_public_library(jar_name):
        with print_lock:
            print(f"  └─ ✅ 公共包(已知公共库)")
        return ("public", jar_path, "known_public")

    artifact_id, version = extract_jar_name_info(jar_path)

    if version and verify_by_artifact_version(artifact_id, version):
        with print_lock:
            print(f"  └─ ✅ 公共包({artifact_id}:{version})")
        return ("public", jar_path, f"{artifact_id}:{version}")

    coords = extract_maven_coords(jar_path)
    if coords:
        group_id, artifact_id_pom, version_pom = coords

        if any(prefix in group_id for prefix in PRIVATE_PREFIXES):
            with print_lock:
                print(f"  └─ ❌ 私人包({group_id}:{artifact_id_pom}:{version_pom})")
            return ("private", jar_path, f"{group_id}:{artifact_id_pom}:{version_pom}")

        if verify_via_pom_url(group_id, artifact_id_pom, version_pom):
            with print_lock:
                print(f"  └─ ✅ 公共包({group_id}:{artifact_id_pom}:{version_pom})")
            return ("public", jar_path, f"{group_id}:{artifact_id_pom}:{version_pom}")

    with print_lock:
        print(f"  └─ ❌ 私人包(无法验证)")
    return ("private", jar_path, "unknown")


def classify_jar_files(root_dir):
    result = {"public": [], "private": []}
    root_dir_abs = os.path.abspath(root_dir)

    print(f"[INFO] 扫描目录: {root_dir_abs}")

    jar_files = []
    for root, dirs, files in os.walk(root_dir_abs):
        for file in files:
            if file.lower().endswith(".jar"):
                jar_files.append(os.path.join(root, file))

    if not jar_files:
        print("[ERROR] 未找到 JAR 文件!")
        return result

    total = len(jar_files)
    print(f"[INFO] 找到 {total} 个 JAR,启动 {THREAD_NUM} 线程...")
    print("=" * 60)

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=THREAD_NUM) as executor:
        future_to_jar = {
            executor.submit(classify_single_jar, jar, idx+1, total): jar
            for idx, jar in enumerate(jar_files)
        }

        for future in as_completed(future_to_jar):
            try:
                res_type, jar_path, info = future.result()
                result[res_type].append((jar_path, info))
            except Exception as e:
                jar_path = future_to_jar[future]
                with print_lock:
                    print(f"[ERROR] {os.path.basename(jar_path)} - {str(e)}")
                result["private"].append((jar_path, "error"))

    elapsed = time.time() - start_time
    print("=" * 60)
    print(f"[INFO] 完成! 耗时: {elapsed:.2f}秒, 速度: {total/elapsed:.2f}个/秒")

    return result


# ============================
# 🔥 新增：解压私有库
# ============================

def extract_private_jars(private_list, output_dir):
    if not output_dir:
        return
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        if not os.path.exists(target_dir):
            os.makedirs(output_dir)
    for jar_path, info in private_list:

        try:
            os.system(f"cp {jar_path} {output_dir}/")
            print(f"[复制] {jar_path} → {output_dir}/")
        except Exception as e:
            print(f"[ERROR] 复制 {jar_path}: {str(e)}")
# ========================================================
# 主入口
# ========================================================
if __name__ == "__main__":
    TARGET_DIR = "./"

    print("=" * 60)
    print("Maven JAR 智能分类工具 (改进版)")
    print("=" * 60)

    classification = classify_jar_files(TARGET_DIR)

    # 新增：自动解压私有包
    if args.output:
        print(f"[INFO] 正在解压私有库到: {args.output}")
        extract_private_jars(classification["private"], args.output)

    # 打印结果（保持原样）
    print("\n" + "=" * 60)
    print("===== 分类结果 =====")
    print("=" * 60)

    print(f"\n✅ 公共包 ({len(classification['public'])} 个):")
    for idx, (jar, info) in enumerate(classification["public"], 1):
        print(f"  {idx}. {os.path.basename(jar)}")
        if info not in ["known_public", "unknown"]:
            print(f"      → {info}")

    print(f"\n❌ 私人包 ({len(classification['private'])} 个):")
    for idx, (jar, info) in enumerate(classification["private"], 1):
        print(f"  {idx}. {os.path.basename(jar)}")
        if info not in ["company_library", "unknown", "error"]:
            print(f"      → {info}")

    total = len(classification['public']) + len(classification['private'])
    print(f"\n总计: {total} | 公共: {len(classification['public'])} ({len(classification['public'])/total*100:.1f}%) | 私人: {len(classification['private'])} ({len(classification['private'])/total*100:.1f}%)")
