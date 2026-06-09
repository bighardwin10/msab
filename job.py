import dotenv
import paramiko
import os
import logging
from stat import S_ISDIR
import shutil
from datetime import date
import time
from onedrive_upload import upload
import sys

def download_remote_folder(sftp, remote_dir, local_dir):
    try:
        os.makedirs(local_dir, exist_ok=True)
        for item in sftp.listdir_attr(remote_dir):
            remote_path = remote_dir + '/' + item.filename
            local_path = os.path.join(local_dir, item.filename)
            if S_ISDIR(item.st_mode):
                download_remote_folder(sftp, remote_path, local_path)
            else:
                logging.info(f"正在下载: {remote_path}")
                sftp.get(remote_path, local_path)
    except FileNotFoundError:
        logging.error(f"远程目录不存在: {remote_dir}")
        raise

dotenv.load_dotenv()
os.makedirs("logs", exist_ok=True)

logging.basicConfig(level=logging.INFO, filename=f"logs/log-{time.time()}.log", force=True, encoding="utf-8")
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

# 读取环境变量
sftp_host = os.environ.get("SFTP_HOST")
sftp_usrname = os.environ.get("SFTP_USERNAME")
sftp_passwd = os.environ.get("SFTP_PASSWD")
sftp_port = int(os.environ.get("SFTP_PORT", 22))
folder_name = os.environ.get("SAVE_FOLDER_NAME")

# 验证必要变量
if not all([sftp_host, sftp_usrname, sftp_passwd, folder_name]):
    logging.error("缺少必要的环境变量 (SFTP_HOST, SFTP_USERNAME, SFTP_PASSWD, SAVE_FOLDER_NAME)")
    sys.exit(1)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    logging.info(f"连接到 {sftp_host}:{sftp_port}")
    ssh.connect(sftp_host, port=sftp_port, password=sftp_passwd, username=sftp_usrname)
    with ssh.open_sftp() as sftp:
        dirs = sftp.listdir()
        if folder_name not in dirs:
            logging.error(f"远程文件夹 '{folder_name}' 不存在")
            sys.exit(1)
        download_remote_folder(sftp, folder_name, folder_name)
except Exception as e:
    logging.error(f"连接或下载失败: {e}")
    sys.exit(1)
finally:
    ssh.close()

# 确认本地目录已下载
if not os.path.isdir(folder_name):
    logging.error(f"本地目录 {folder_name} 不存在，下载失败")
    sys.exit(1)

dest_file = f"{folder_name}-backup-{date.today().strftime('%Y%m%d')}"
shutil.make_archive(dest_file, "zip", folder_name)
logging.info("压缩完成！")

tenant_id = os.environ.get("TENANT_ID")
client_id = os.environ.get("CLIENT_ID")
client_secret = os.environ.get("CLIENT_SECRET")

if not all([tenant_id, client_id, client_secret]):
    logging.error("缺少 OneDrive 上传所需的凭证")
    sys.exit(1)

try:
    upload(
        file_path=dest_file + ".zip",
        destination_path=f"backups/{dest_file}.zip",
        app_id=client_id,
        secret=client_secret,
        tenant=tenant_id,
        user="srvbkup@2dt0.de"
    )
    logging.info("上传成功！")
except Exception as e:
    logging.error(f"上传失败: {e}")
    sys.exit(1)
finally:
    # 清理临时文件
    shutil.rmtree(folder_name, ignore_errors=True)
    if os.path.exists(dest_file + ".zip"):
        os.remove(dest_file + ".zip")
    logging.info("清理完成")