import os
import random

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from DrissionPage import ChromiumOptions, Chromium
from DrissionPage import SessionPage
import uvicorn
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

import logging
import traceback

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
tr = traceback

app = FastAPI(title="ChatGPT Login Service")

proxy_config = os.getenv("PROXY_POOL", None)

proxies = [] if proxy_config is None else proxy_config.split(",")
print(f"proxies: {proxies}")

page = SessionPage()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: Optional[str]
    status: str
    message: str


redirect_step = 0


def get_turnstile_token(tab):
    try:
        logger.info('等待验证框加载...')
        tab.wait.ele_displayed('@name=cf-turnstile-response', timeout=10)
        if tab.ele('@name=cf-turnstile-response'):
            logger.info("验证框加载完成")
            challenge_solution = tab.ele("@name=cf-turnstile-response")
            challenge_wrapper = challenge_solution.parent()
            challenge_iframe = challenge_wrapper.shadow_root.ele("tag:iframe")
            challenge_iframe_body = challenge_iframe.ele("tag:body")
            challenge_button = challenge_iframe_body.sr("tag:input")
            challenge_button.click()
            logger.info("验证按钮已点击，等待验证完成...")
        else:
            logger.info("验证框未加载，跳过")
    except Exception as e:
        logger.error(f"处理验证失败: {str(e)}")
        download_html(tab, "cf5s-error")
        raise


def check_turnstile(tab):
    if tab.ele('@name=cf-turnstile-response'):
        print('\n', "准备处理验证框...")
        get_turnstile_token(tab)
        tab.wait.ele_displayed('t:textarea', timeout=10)
        if tab.ele('t:textarea'):
            print('\n', '页面加载完成')
        elif tab.ele('@class=btn relative btn-blue btn-large'):
            print('\n', '另一种界面加载完成')


def perform_login(account: str, password: str):
    EXTENSION_PATH = "plugins/turnstilePatch"
    co = ChromiumOptions().set_paths(browser_path=r'/user/bin/google-chrome')
    co.add_extension(EXTENSION_PATH)
    if len(proxies) > 0:
        co.set_proxy(random.choice(proxies))
    co.headless()
    co.set_user_agent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.92 Safari/537.36')
    co.set_pref('credentials_enable_service', False)
    co.set_pref('profile.password_manager_enabled', False)
    # 额外浏览器参数
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-gpu')
    browser = Chromium(co)

    """执行登录流程"""
    print('\n', '开始执行登录流程')

    try:
        tab = browser.new_tab()
        tab.run_js("try { turnstile.reset() } catch(e) { }")
        return step1(tab, account, password, browser)

    except Exception as e:
        print(f"错误堆栈: {traceback.format_exc()}")
        return {
            "status": "error",
            "message": f"发生错误{traceback.format_exc()}",
            "access_token": None
        }
    finally:
        print(f"退出浏览器")
        global redirect_step
        redirect_step = 0
        browser.clear_cache()
        browser.quit()


def step1(tab, account, password, browser):
    global redirect_step
    redirect_step = 1
    print("步骤1: 开始访问网站...")

    try:
        tab.get('https://chatgpt.com')
        print('请耐心等待页面加载...')
        tab.wait.ele_displayed('t:textarea', timeout=30)
        check_turnstile(tab)
        print('正在加载中...')
        if tab.ele('t:textarea'):
            print('\n', '页面加载完成')

        elif tab.ele('@class=btn relative btn-blue btn-large'):
            print('\n', '另一种界面加载完成')
        else:
            download_html(tab, "login-page-error")
            return {
                "status": "error",
                "message": "加载登录页异常",
                "access_token": None
            }
        check_turnstile(tab)
        return step2(tab, account, password, browser)

    except Exception as e:
        print('\n', f"openai页面自动跳转:{e}，发生位置：Step{redirect_step}")
        if redirect_step == 1:
            return step3(tab, account, password, browser)
        else:
            download_html(tab, "page-redirect-problem")
            return {
                "status": "error",
                "message": "页面自动跳转",
                "access_token": None
            }


def step2(tab, account, password, browser):
    global redirect_step
    redirect_step = 2
    print('\n', "步骤2: 开始登录...")

    try:
        '''
        这里可以看到，先尝试直接点击登录按钮，点击按钮时会报错: 该元素没有位置及大小。
        然后尝试点击注册按钮，加载注册界面后再点击登录
        '''
        tab.wait.ele_displayed(
            'xpath:/html/body/div[1]/div[1]/main/div[1]/div[1]/div/div[1]/div/div[3]/div/button[1]', timeout=10)
        signin_btn = tab.ele('xpath:/html/body/div[1]/div[1]/main/div[1]/div[1]/div/div[1]/div/div[3]/div/button[1]')
        if signin_btn:
            print('\n', "找到黑色登录按钮:", signin_btn.text)
        else:
            signin_btn = tab.wait.ele_displayed('@data-testid=login-button', timeout=10)
            print('\n', "找到蓝色登录按钮:", signin_btn.text)
        try:
            signin_btn.click()
            return step3(tab, account, password, browser)
        except Exception as e:
            print(f"处理登录按钮时出错: {str(e)}")
        tab.wait.ele_displayed('@class=btn relative btn-secondary btn-small', timeout=10)
        signup_btn = tab.ele('@class=btn relative btn-secondary btn-small')
        if signup_btn:
            print('\n', "找到注册按钮:", signup_btn.text)
            signup_btn.click()
            print('\n', "点击注册按钮")

        check_turnstile(tab)
        tab.wait.ele_displayed('@class=other-page-link', timeout=10)
        signin_btn = tab.ele('@class=other-page-link')
        if signin_btn:
            print('\n', "找到跳转登录链接:", signin_btn.text)
            signin_btn.click()
            print('\n', "点击跳转登录链接")
        else:
            check_turnstile(tab)
            tab.wait.ele_displayed('@class=other-page-link', timeout=10)
            signin_btn = tab.ele('@class=other-page-link')
            if signin_btn:
                print('\n', "找到跳转登录链接:", signin_btn.text)
                signin_btn.click()
                print('\n', "点击跳转登录链接")
            else:
                print("未找到登录链接")
                download_html(tab, "login-link-not-found")

        check_turnstile(tab)

    except Exception as e:
        print(f"处理注册按钮时出错: {str(e)}")
        traceback.print_exc()
        return {
            "status": "error",
            "message": "处理注册按钮时出错",
            "access_token": None
        }
    return step3(tab, account, password, browser)


def step3(tab, account, password, browser):
    global redirect_step
    redirect_step = 3
    print('\n', "步骤3: 输入邮箱...")
    try:
        check_turnstile(tab)
        tab.wait.ele_displayed('@id=email-input', timeout=10)
        if tab.ele('@id=email-input'):
            print('\n', "邮箱输入框加载完成")
        tab.actions.click('@id=email-input').type(account)
        tab.wait(1)
        tab.ele('@class=continue-btn').click()
        print('\n', "输入邮箱并点击继续")
    except Exception as e:
        # 打印页面存储到pic目录
        download_html(tab, "email-input-error")
        print(f"加载邮箱输入框时出错: {str(e)}")
        return {
            "status": "error",
            "message": "加载邮箱输入框时出错",
            "access_token": None
        }

    tab.wait(5)
    return step4(tab, account, password, browser)


def step_auth0(tab, account, password, browser):
    global redirect_step
    redirect_step = 3
    print('\n', "进入步骤auth 0: 输入邮箱...")
    try:
        check_turnstile(tab)
        tab.wait.ele_displayed('@id=email-or-phone-input', timeout=10)
        if tab.ele('@id=email-or-phone-input'):
            print('\n', "邮箱输入框加载完成")
        tab.actions.click('@id=email-or-phone-input').type(account)
        tab.wait(0.5)
        tab.ele('@class=continue-btn').click()
        print('\n', "输入邮箱并点击继续")
    except Exception as e:
        # 打印页面存储到pic目录
        download_html(tab, "email-input-error")
        print(f"加载邮箱输入框时出错: {str(e)}")
        return {
            "status": "error",
            "message": "加载邮箱输入框时出错",
            "access_token": None
        }

    tab.wait(5)
    return step4(tab, account, password, browser)


def step4(tab, account, password, browser):
    global redirect_step
    redirect_step = 4
    print('\n', "步骤4: 输入密码...")

    check_turnstile(tab)

    try:
        # tab.wait.ele_displayed('获取您的 SSO 信息时出错')
        # if tab.ele('获取您的 SSO 信息时出错'):
        tab.wait.ele_displayed('@class=content-wrapper', timeout=10)
        title_element = tab.ele('@class=content-wrapper')
        if title_element and (
                "获取您的 SSO 信息时出错" in title_element.text
                or "Something went wrong while getting your SSO info" in title_element.text):
            print('\n', '检测到 SSO 错误，检查url：' + tab.url)
            # 查找url中第一个auth字符串
            auth_index = tab.url.find('auth')
            # 如果存在auth字符串，则替换auth为auth0
            if auth_index != -1:
                url = tab.url[:auth_index] + 'auth0' + tab.url[auth_index + 4:]
                tab.get(url)
                print('\n', '已尝试替换url:' + tab.url)
                return step_auth0(tab, account, password, browser)
            else:
                print('\n', '未找到auth字符串')
                return {
                    "status": "error",
                    "message": "检测到 SSO 错误，脚本终止，请手动登录",
                    "access_token": None
                }
        else:
            tab.wait.ele_displayed('@id=password', timeout=10)
            if tab.ele('@id=password'):
                print('\n', "密码输入框加载完成")
            else:
                check_turnstile(tab)
                tab.wait.ele_displayed('@id=password', timeout=10)
                if tab.ele('@id=password'):
                    print('\n', "密码输入框加载完成")

            tab.actions.click('@id=password').input(password)
            tab.wait(2)
            tab.actions.click('@type=submit')
            print('\n', "输入密码并点击登录")

    except Exception as e:
        print(f"输入密码时出错: {str(e)}")
        traceback.print_exc()
        download_html(tab, "input-password-error")
        return {
            "status": "error",
            "message": f"输入密码时出错: {str(e)}",
            "access_token": None
        }

    tab.wait(5)
    return step5(tab, account, password, browser)


def step5(tab, account, password, browser):
    global redirect_step
    redirect_step = 5
    print('\n', "步骤5: 获取access_token...")

    tab.wait.ele_displayed('What can I help with?', timeout=30)
    help_title = tab.ele('What can I help with?')
    if help_title:
        print('\n', '登录成功！')
    else:
        print('\n', '登录遇到问题，请检查用户名密码是否正确')
        download_html(tab, "login-problem")
        return {
            "status": "error",
            "message": "登录可能遇到问题",
            "access_token": None
        }

    tab.wait.ele_displayed('Resend email', timeout=10)
    verify_code = tab.ele('Resend email')
    if verify_code:
        print('\n', '提示需要邮箱验证码，脚本终止，请手动获取')
        return {
            "status": "error",
            "message": "提示需要邮箱验证码，脚本终止，请手动获取",
            "access_token": None
        }

    browser.new_tab('https://chatgpt.com/api/auth/session')
    tab = browser.latest_tab
    tab.get('https://chatgpt.com/api/auth/session')
    tab.wait(5)
    download_html(tab, "access-token-get-page")

    response_json = tab.json
    if response_json and 'accessToken' in response_json:
        access_token = response_json['accessToken']
        print('\n', "请复制并保存你的access_token:", '\n')
        print(access_token)
        return {
            "status": "success",
            "message": "登录成功",
            "access_token": access_token
        }

    else:
        print("错误:未找到access token")
        download_html(tab, "access-token-not-found")
        return {
            "status": "error",
            "message": "未找到access token,请检查账号密码是否正确",
            "access_token": None
        }


def download_html(tab, name: str = "info"):
    """
    下载当前页面的HTML源代码

    :param tab: DrissionPage的tab对象
    :return: HTML文件路径
    """
    html_content = tab.html
    file_path = f"pages/{name}.html"

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML已保存到: {file_path}")
    return file_path


# 创建线程池
executor = ThreadPoolExecutor(max_workers=3)


@app.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    try:
        # 在线程池中执行浏览器操作
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            perform_login,
            request.email,
            request.password
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return result
    except Exception as e:
        # 打印报错
        logger.error(f"API错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
