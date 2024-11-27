# chatgpt_at_helper

基于DrissionPage的自动化chatgpt access_token获取
支持http/https的代理服务器

灵感源自：
https://github.com/hmhm2022/gpt-cursor-auto

使用方法：
curl -X POST "http://localhost:8000/login" \\n     -H "Content-Type: application/json" \\n     -d '{"email":"你的邮箱","password":"你的密码"}'

