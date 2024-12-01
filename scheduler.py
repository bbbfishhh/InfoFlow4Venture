import schedule
import time
import logging
import sys
import os
import signal
import json
import subprocess
from datetime import datetime
import pytz

class TaskScheduler:
    def __init__(self, config_path='scheduler_config.json'):
        # 创建日志目录
        log_dir = './logs'
        os.makedirs(log_dir, exist_ok=True)

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s: %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'scheduler.log')),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # 配置文件路径
        self.config_path = config_path
        
        # 读取配置
        self.load_config()
        
        # 进程ID文件
        self.pid_file = os.path.join(log_dir, 'scheduler.pid')
        
        # 停止标志
        self.running = False

        # 设置时区为北京时间
        self.beijing_tz = pytz.timezone('Asia/Shanghai')
        
    def load_config(self):
        """加载配置文件"""
        try:
            load_config_path = os.path.join('./logs', self.config_path)
            with open(load_config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            # 默认配置
            self.config = {
                "crawler_times": ["08:00"],
                "email_times": ["16:25"],
                "crawler_script": "ListPageExtractor.py",
                "email_script": "EmailService.py"
            }
            self.save_config()
        
    def save_config(self):
        """保存配置文件"""
        save_config_path = os.path.join('./logs', self.config_path)
        with open(save_config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
    
    def run_script(self, script_path):
        """执行Python脚本并记录详细日志"""
        log_dir = './logs'
        log_file_path = os.path.join(log_dir, f'{os.path.basename(script_path)}_exec.log')
        
        try:
            # 获取北京时间
            beijing_time = datetime.now(self.beijing_tz)
            exec_time = beijing_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 记录执行日志
            self.logger.info(f"执行 {script_path} 于 {exec_time}")
            
            # 执行脚本并记录输出
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"\n--- 执行时间: {exec_time} ---\n")
                
                result = subprocess.run(
                    ['python3', script_path], 
                    capture_output=True, 
                    text=True
                )
                
                # 写入标准输出
                log_file.write(result.stdout)
                log_file.write("\n")
                
                # 写入错误输出
                if result.stderr:
                    log_file.write(f"错误信息:\n{result.stderr}\n")
                
                log_file.write(f"--- 执行结束: {datetime.now(self.beijing_tz).strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            
            # 记录执行结果
            self.logger.info(f"执行 {script_path} 完成")
            
        except Exception as e:
            self.logger.error(f"执行 {script_path} 失败: {e}")
    
    def setup_schedule(self):
        """设置定时任务"""
        # 清除所有已存在的任务
        schedule.clear()
        
        # 添加爬虫任务
        for time_str in self.config.get('crawler_times', []):
            schedule.every().day.at(time_str).do(
                self.run_script, 
                self.config.get('crawler_script', 'ListPageExtractor.py')
            )
            self.logger.info(f"设置爬虫任务于 {time_str}")
        
        # 添加邮件任务  
        for time_str in self.config.get('email_times', []):
            schedule.every().day.at(time_str).do(
                self.run_script, 
                self.config.get('email_script', 'EmailService.py')
            )
            self.logger.info(f"设置邮件服务任务于 {time_str}")
    
    def run(self):
        """运行调度器"""
        self.setup_schedule()
        self.running = True
        self.logger.info("调度器已启动")
        
        while self.running:
            schedule.run_pending()
            time.sleep(1)
    
    def start(self):
        """启动守护进程"""
        pid = os.fork()
        if pid == 0:  # 子进程
            self.run()
        else:  # 父进程
            with open(self.pid_file, 'w') as f:
                f.write(str(pid))
            self.logger.info(f"守护进程已启动，PID: {pid}")
    
    def stop(self):
        """停止调度器"""
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read())
            os.kill(pid, signal.SIGTERM)
            os.remove(self.pid_file)
            self.logger.info("调度器已停止")
        except FileNotFoundError:
            self.logger.warning("未找到调度器进程")
        except Exception as e:
            self.logger.error(f"停止失败: {e}")
    
    def set_times(self, task_type, times):
        """设置执行时间"""
        if task_type == 'crawler':
            self.config['crawler_times'] = times
        elif task_type == 'email':
            self.config['email_times'] = times
        
        self.save_config()
        self.logger.info(f"{task_type}任务时间已更新为: {times}")
        
        # 重新加载调度
        self.setup_schedule()

def main():
    scheduler = TaskScheduler()
    
    if len(sys.argv) < 2:
        print("用法: python scheduler.py [start|stop|set_crawler_time|set_email_time]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'start':
        scheduler.start()
    elif command == 'stop':
        scheduler.stop()
    elif command == 'set_crawler_time':
        if len(sys.argv) < 3:
            print("请提供新的爬虫执行时间，如: 09:00 10:30")
            sys.exit(1)
        scheduler.set_times('crawler', sys.argv[2:])
    elif command == 'set_email_time':
        if len(sys.argv) < 3:
            print("请提供新的邮件发送时间，如: 17:00 18:30")
            sys.exit(1)
        scheduler.set_times('email', sys.argv[2:])

if __name__ == '__main__':
    main()