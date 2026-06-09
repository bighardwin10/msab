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
        # 确保本地目录存在
        os.makedirs(local_dir, exist_ok=True)
        
        # 列出远程目录内容
        for item in sftp.listdir_attr(remote_dir):
            remote_path = remote_dir + '/' + item.filename
            local_path = os.path.join(local_dir, item.filename)
            
            # 判断是否为目录
            if S_ISDIR(item.st_mode):
                # 递归下载子文件夹
                download_remote_folder(sftp, remote_path, local_path)
            else:
                # 下载文件
                logging.info(f"正在下载: {remote_path}")
                sftp.get(remote_path, local_path)
    except FileNotFoundError:
        logging.info(f"远程目录不存在: {remote_dir}")

dotenv.load_dotenv()

os.makedirs("logs",exist_ok=True)

logging.basicConfig(level=logging.INFO,filename=f"logs/log-{time.time()}.log",force=True,encoding="utf-8")
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

# 从服务器拉取存档
sftp_host = os.environ["SFTP_HOST"]
sftp_usrname = os.environ["SFTP_USERNAME"]
sftp_passwd = os.environ["SFTP_PASSWD"]
sftp_port = int(os.environ.get("SFTP_PORT",22))
folder_name = os.environ["SAVE_FOLDER_NAME"]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(sftp_host,port=sftp_port,password=sftp_passwd,username=sftp_usrname)
    with ssh.open_sftp() as sftp:
        dirs = sftp.listdir()
        if folder_name not in dirs:
            logging.error(f"存档文件夹: {folder_name} 未找到！")
            os._exit(1)
        download_remote_folder(sftp,folder_name,folder_name)
except Exception as e:
    print(f"发生错误: {e}")
finally:
    # 5. 关闭连接
    ssh.close()

dest_file = f"{folder_name}-backup-{date.today().strftime('%Y%m%d')}"
shutil.make_archive(dest_file,"zip",folder_name)
logging.info("压缩完成！")

# 上传到Onedrive
tenant_id = os.environ["TENANT_ID"]
client_id = os.environ["CLIENT_ID"]
client_secret = os.environ["CLIENT_SECRET"]

upload(
    file_path=dest_file + ".zip",
    destination_path=f"backups/{dest_file}.zip",
    app_id=client_id,
    secret=client_secret,
    tenant=tenant_id,
    user="srvbkup@2dt0.de"
)
logging.info("上传成功！")