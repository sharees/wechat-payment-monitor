import PyInstaller.__main__
import os
import sys

def build_exe():
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 定义需要打包的文件
    main_script = os.path.join(current_dir, 'main.py')
    
    # 定义需要包含的数据文件
    datas = [
        f'demo.html{os.pathsep}.',
        f'.env{os.pathsep}.',
    ]
    
    # 定义需要包含的包
    hidden_imports = [
        'flask',
        'flask_cors',
        'uiautomation',
        'win32api',
        'win32con',
        'win32gui',
        'psutil',
        'aiohttp',
        'asyncio',
        'loguru',
        'python-dotenv'
    ]
    
    # 构建 PyInstaller 参数
    args = [
        main_script,
        '--name=WeChatPay',
        '--onefile',  # 打包成单个文件
        '--clean',  # 清理临时文件
    ]
    
    # 添加数据文件
    for data in datas:
        args.append(f'--add-data={data}')
    
    # 添加隐藏导入
    for imp in hidden_imports:
        args.append(f'--hidden-import={imp}')
    
    # 运行 PyInstaller
    PyInstaller.__main__.run(args)

if __name__ == '__main__':
    build_exe() 