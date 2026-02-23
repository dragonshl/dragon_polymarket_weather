#!/usr/bin/env python3
"""
Git Web Interface
简单Git可视化界面
"""

import subprocess
import http.server
import socketserver
import os
from pathlib import Path

PORT = 8080

def get_git_info():
    """获取Git信息"""
    info = {}
    
    # 分支
    try:
        result = subprocess.run(['git', 'branch'], capture_output=True, text=True, cwd='.')
        info['branches'] = [b.strip().replace('* ', '') for b in result.stdout.strip().split('\n') if b]
    except:
        info['branches'] = []
    
    # 最近提交
    try:
        result = subprocess.run(['git', 'log', '--oneline', '-10'], capture_output=True, text=True, cwd='.')
        info['commits'] = result.stdout.strip().split('\n')
    except:
        info['commits'] = []
    
    # 状态
    try:
        result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True, cwd='.')
        info['status'] = result.stdout.strip().split('\n')
    except:
        info['status'] = []
    
    # 文件列表
    try:
        result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, cwd='.')
        info['files'] = result.stdout.strip().split('\n')[:50]  # 前50个文件
    except:
        info['files'] = []
    
    return info

def generate_html():
    """生成HTML页面"""
    info = get_git_info()
    
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>总控龙宝 Git 仓库</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }
        h1 { color: #00d9ff; }
        h2 { color: #ff6b6b; border-bottom: 1px solid #333; padding-bottom: 5px; }
        .card { background: #16213e; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .branch { color: #00ff88; margin: 5px 0; }
        .commit { color: #ffd93d; font-family: monospace; }
        .file { color: #6bcfff; font-family: monospace; }
        .status { color: #ff6b6b; }
        a { color: #00d9ff; }
    </style>
</head>
<body>
    <h1>🐉 总控龙宝 Git 仓库</h1>
    
    <div class="card">
        <h2>📂 分支 (Branches)</h2>
"""
    
    for branch in info.get('branches', []):
        html += f'<div class="branch">* {branch}</div>'
    
    html += """
    </div>
    
    <div class="card">
        <h2>📜 最近提交 (Recent Commits)</h2>
"""
    
    for commit in info.get('commits', []):
        if commit:
            html += f'<div class="commit">{commit}</div>'
    
    html += """
    </div>
    
    <div class="card">
        <h2>📁 跟踪的文件 (Tracked Files)</h2>
"""
    
    for f in info.get('files', []):
        if f:
            html += f'<div class="file">{f}</div>'
    
    html += """
    </div>
    
    <div class="card">
        <h2>⚡ 工作区状态</h2>
"""
    
    if info.get('status'):
        for s in info.get('status', []):
            if s:
                html += f'<div class="status">{s}</div>'
    else:
        html += '<div>工作区干净</div>'
    
    html += """
    </div>
    
    <hr>
    <p><a href="?action=refresh">🔄 刷新</a> | 
       <a href="?action=log">📜 完整提交历史</a></p>
    
    <footer>
        <p>总控龙宝交易系统 v1.2 | Git仓库</p>
    </footer>
</body>
</html>
"""
    return html

class GitHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or '?' not in self.path:
            html = generate_html()
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        elif 'action=log' in self.path:
            result = subprocess.run(['git', 'log', '--oneline', '--all'], capture_output=True, text=True)
            commits = result.stdout
            
            html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Git Log</title>
<style>
body {{ font-family: monospace; background: #1a1a2e; color: #eee; padding: 20px; }}
.commit {{ color: #ffd93d; }}
a {{ color: #00d9ff; }}
</style>
</head>
<body>
<h1>📜 完整提交历史</h1>
<pre class="commit">{commits}</pre>
<p><a href="/">← 返回</a></p>
</body>
</html>"""
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
    
    def log_message(self, format, *args):
        pass  # 禁用日志

if __name__ == '__main__':
    os.chdir(Path(__file__).parent)
    print(f"🐉 Git Web Interface 启动中...")
    print(f"访问地址: http://localhost:{PORT}")
    print(f"按 Ctrl+C 停止")
    
    with socketserver.TCPServer(("", PORT), GitHandler) as httpd:
        httpd.serve_forever()
