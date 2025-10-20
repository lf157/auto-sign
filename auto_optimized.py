import time
import random
import os
from playwright.sync_api import sync_playwright

def load_accounts(filename='anyrouter-accounts.txt'):
    """从文件加载账号列表"""
    accounts = []
    if not os.path.exists(filename):
        print(f"错误: 账号文件 {filename} 不存在！")
        return accounts

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # 跳过空行和注释行
                if not line or line.startswith('#'):
                    continue

                # 解析账号密码
                if ',' in line:
                    parts = line.split(',', 1)
                    if len(parts) == 2:
                        username, password = parts[0].strip(), parts[1].strip()
                        if username and password:
                            accounts.append({'username': username, 'password': password})
                        else:
                            print(f"警告: 第 {line_num} 行格式不正确，已跳过")
                    else:
                        print(f"警告: 第 {line_num} 行格式不正确，已跳过")
                else:
                    print(f"警告: 第 {line_num} 行缺少逗号分隔符，已跳过")

        print(f"成功加载 {len(accounts)} 个账号")
        return accounts

    except Exception as e:
        print(f"读取账号文件失败: {e}")
        return accounts

# 从文件加载账号列表
accounts = load_accounts('anyrouter-accounts.txt')

login_url = 'https://anyrouter.top/login'

def get_balance_info(page):
    """获取账户余额信息 - 基于实际页面结构优化"""
    try:
        balance_info = {}
        

        # 方法0: 直接调用 /api/user/self API 获取余额（新增 - 最可靠）
        try:
            print(f"[*] 方法0: 通过 API 调用获取余额...")

            # 先从 localStorage 获取 user_id（API 需要 new-api-user header）
            user_id = page.evaluate("""() => {
                try {
                    const user = JSON.parse(localStorage.getItem('user') || '{}');
                    return user.id || null;
                } catch(e) {
                    return null;
                }
            }""")

            if not user_id:
                print(f"[!] 方法0失败: 无法从 localStorage 获取 user_id")
            else:
                # 使用 fetch 调用 API（带上必需的 header）
                api_response = page.evaluate("""
                    async (userId) => {
                        try {
                            const response = await fetch('/api/user/self', {
                                method: 'GET',
                                headers: {
                                    'Accept': 'application/json',
                                    'new-api-user': userId.toString()
                                }
                            });
                            const data = await response.json();
                            return data;
                        } catch(e) {
                            return null;
                        }
                    }
                """, user_id)

                if api_response and api_response.get("success") and api_response.get("data"):
                    user_data = api_response["data"]

                    # quota 就是当前余额，used_quota 是历史消耗
                    remaining = user_data["quota"] / 500000
                    used_quota = user_data["used_quota"] / 500000

                    balance_info["api_remaining"] = f"${remaining:.2f}"
                    balance_info["api_used"] = f"${used_quota:.2f}"
                    balance_info["api_requests"] = str(user_data["request_count"])
                    balance_info["username"] = user_data.get("display_name") or user_data.get("username", "")

                    print(f"[+] 方法0成功: 余额=${remaining:.2f}, 已用=${used_quota:.2f}, 请求={user_data['request_count']}")
                else:
                    print(f"[!] 方法0失败: API返回无效数据")

        except Exception as e:
            print(f"[!] 方法0异常: {e}")

        # 方法1: 直接通过文本内容和上下文获取余额信息
        try:
            # 获取所有包含美元符号的元素
            balance_data = page.evaluate('''
                () => {
                    const result = {};
                    
                    // 查找所有包含美元符号的元素
                    const dollarElements = Array.from(document.querySelectorAll('*')).filter(el => 
                        el.textContent && 
                        el.textContent.match(/\\$[0-9,]+\\.?[0-9]*/) && 
                        el.children.length === 0  // 只要叶子节点
                    );
                    
                    dollarElements.forEach(el => {
                        const text = el.textContent.trim();
                        const parent = el.parentElement;
                        const grandParent = parent ? parent.parentElement : null;
                        
                        // 构建上下文
                        let context = '';
                        if (parent) context += parent.textContent;
                        if (grandParent) context += ' | ' + grandParent.textContent;
                        
                        // 根据上下文分类
                        if (context.includes('当前余额')) {
                            result.currentBalance = text;
                        } else if (context.includes('历史消耗')) {
                            result.historicalUsage = text;
                        } else if (context.includes('统计额度')) {
                            result.statisticsQuota = text;
                        }
                    });
                    
                    // 查找请求次数等数字信息
                    const numberElements = Array.from(document.querySelectorAll('*')).filter(el => 
                        el.textContent && 
                        el.textContent.match(/^"?[0-9,]+"?$/) && 
                        el.children.length === 0
                    );
                    
                    numberElements.forEach(el => {
                        const text = el.textContent.trim().replace(/"/g, '');
                        const parent = el.parentElement;
                        const grandParent = parent ? parent.parentElement : null;
                        
                        let context = '';
                        if (parent) context += parent.textContent;
                        if (grandParent) context += ' | ' + grandParent.textContent;
                        
                        if (context.includes('请求次数')) {
                            result.requestCount = text;
                        } else if (context.includes('统计次数')) {
                            result.statisticsCount = text;
                        } else if (context.includes('统计Tokens')) {
                            result.statisticsTokens = text;
                        }
                    });
                    
                    return result;
                }
            ''')
            
            if balance_data:
                balance_info.update(balance_data)
                
        except Exception as e:
            print(f"[*] 方法1获取余额失败: {e}")
        
        # 方法2: 通过localStorage获取用户数据
        try:
            user_data = page.evaluate('''
                () => {
                    try {
                        const userStr = localStorage.getItem('user');
                        if (userStr) {
                            const user = JSON.parse(userStr);
                            return {
                                quota: user.quota || 0,
                                used_quota: user.used_quota || 0,
                                request_count: user.request_count || 0,
                                username: user.username || '',
                                display_name: user.display_name || ''
                            };
                        }
                    } catch(e) {
                        console.log('localStorage解析失败:', e);
                    }
                    return null;
                }
            ''')
            
            if user_data:
                # 计算剩余额度 (根据网站的计费规则)
                total_quota = user_data.get('quota', 0) / 500000  # 500000 units = $1
                used_quota = user_data.get('used_quota', 0) / 500000
                remaining = total_quota - used_quota
                
                balance_info['localStorage_remaining'] = f"${remaining:.2f}"
                balance_info['localStorage_total'] = f"${total_quota:.2f}"
                balance_info['localStorage_used'] = f"${used_quota:.2f}"
                balance_info['localStorage_requests'] = str(user_data.get('request_count', 0))
                balance_info['username'] = user_data.get('display_name') or user_data.get('username', '')
                
        except Exception as e:
            print(f"[*] 方法2获取用户数据失败: {e}")
        
        # 格式化输出
        if balance_info:
            result_parts = []
            
            # 优先显示API方法获取的余额信息
            if 'api_remaining' in balance_info:
                result_parts.append(f"💰 当前余额: {balance_info['api_remaining']}")
            elif 'currentBalance' in balance_info:
                result_parts.append(f"💰 当前余额: {balance_info['currentBalance']}")
            elif 'localStorage_remaining' in balance_info:
                result_parts.append(f"💰 剩余额度: {balance_info['localStorage_remaining']}")
                
            if 'api_used' in balance_info:
                result_parts.append(f"📊 历史消耗: {balance_info['api_used']}")
            elif 'historicalUsage' in balance_info:
                result_parts.append(f"📊 历史消耗: {balance_info['historicalUsage']}")
            elif 'localStorage_used' in balance_info:
                result_parts.append(f"📊 已用额度: {balance_info['localStorage_used']}")
                
            if 'api_requests' in balance_info:
                result_parts.append(f"🔢 请求次数: {balance_info['api_requests']}")
            elif 'requestCount' in balance_info:
                result_parts.append(f"🔢 请求次数: {balance_info['requestCount']}")
            elif 'localStorage_requests' in balance_info:
                result_parts.append(f"🔢 请求次数: {balance_info['localStorage_requests']}")
                
            if 'statisticsQuota' in balance_info and balance_info['statisticsQuota'] != '$0.00':
                result_parts.append(f"📈 统计额度: {balance_info['statisticsQuota']}")
                
            if 'username' in balance_info:
                result_parts.append(f"👤 用户: {balance_info['username']}")
            
            return " | ".join(result_parts) if result_parts else None
        
        return None
        
    except Exception as e:
        print(f"[*] 获取余额信息时出错: {e}")
        return None

def optimized_login_and_sign(account):
    """优化版浏览器自动登录和签到"""
    print(f"[*] 正在处理账号: {account['username']}")
    
    balance_info = None  # 存储余额信息
    
    try:
        with sync_playwright() as p:
            # 使用无头浏览器，提高速度
            browser = p.chromium.launch(
                headless=True,  # 无头模式，不显示窗口
                # 自动选择 Chromium (兼容 GitHub Actions)
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',  # 避免被检测为自动化
                    '--disable-extensions',
                    '--no-first-run',
                    '--disable-default-apps',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection'
                ]
            )
            
            # 创建页面并设置更快的超时
            page = browser.new_page()
            page.set_default_timeout(10000)  # 10秒超时
            
            # 设置更真实的用户代理
            page.set_extra_http_headers({
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            print(f"[*] 访问登录页面...")
            page.goto(login_url, wait_until='domcontentloaded')  # 只等待DOM加载，不等待所有资源

            # 增强弹窗处理
            try:
                # 方法1: 按 ESC 键关闭弹窗
                page.keyboard.press('Escape')
                time.sleep(0.5)

                # 方法2: 点击关闭按钮
                close_button = page.locator('button:has-text("关闭公告"), button:has-text("关闭"), .semi-modal-close').first
                if close_button.is_visible(timeout=1000):
                    close_button.click()
                    print(f"[*] 关闭了弹窗")
                    time.sleep(0.5)

                # 方法3: 使用 JavaScript 强制移除所有弹窗
                page.evaluate("""() => {
                    const portals = document.querySelectorAll('.semi-portal, .semi-modal, .semi-dialog');
                    portals.forEach(el => el.remove());
                }""")
            except:
                pass

            # 检查是否需要点击邮箱登录选项
            try:
                email_login_button = page.locator('button:has-text("使用 邮箱或用户名 登录")')
                if email_login_button.is_visible(timeout=2000):
                    email_login_button.click()
                    print(f"[*] 点击了邮箱登录选项")
                    time.sleep(1)  # 短暂等待表单出现
            except:
                pass

            # 快速填写登录信息
            print(f"[*] 填写登录信息...")

            # 填写用户名
            username_input = page.locator('#username, input[placeholder*="用户名"], input[placeholder*="邮箱"]').first
            username_input.fill(account['username'])

            # 填写密码
            password_input = page.locator('#password, input[type="password"]').first
            password_input.fill(account['password'])

            print(f"[*] 提交登录...")

            # 登录前再次确保没有弹窗遮挡
            try:
                page.keyboard.press('Escape')
                page.evaluate("""() => {
                    const portals = document.querySelectorAll('.semi-portal, .semi-modal');
                    portals.forEach(el => el.remove());
                }""")
            except:
                pass

            # 点击登录按钮（使用强制点击）
            login_button = page.locator('button:has-text("继续"), button[type="submit"], button:has-text("登录")').first
            login_button.click(force=True)  # 强制点击，忽略遮挡
            
            # 等待登录结果 - 检查URL变化或成功提示
            try:
                # 方法1: 等待URL跳转到控制台
                page.wait_for_url('**/console**', timeout=8000)
                print(f"[+] 账号 {account['username']} 登录成功！")
                
            except:
                try:
                    # 方法2: 等待成功提示出现
                    page.wait_for_selector('text=登录成功', timeout=3000)
                    print(f"[+] 账号 {account['username']} 登录成功！")
                except:
                    # 方法3: 检查是否有错误信息
                    if page.locator('text=密码错误, text=账号不存在, text=验证失败').first.is_visible(timeout=1000):
                        print(f"[!] 账号 {account['username']} 登录失败 - 账号或密码错误")
                        return False
                    else:
                        print(f"[+] 账号 {account['username']} 可能登录成功（未检测到错误）")
            
            # 额外等待，确保页面完全加载
            time.sleep(2)
            
            # 检查当前URL，确认是否在控制台页面
            current_url = page.url
            if 'console' in current_url or 'dashboard' in current_url:
                print(f"[+] 确认已进入控制台页面")
                
                # 等待页面完全加载
                time.sleep(2)
                
                
                # 尝试自动签到（如果页面有签到功能）
                try:
                    # 查找签到按钮或链接
                    sign_in_selectors = [
                        'button:has-text("签到")',
                        'button:has-text("打卡")', 
                        'a:has-text("签到")',
                        '[data-testid="sign-in"]',
                        '.sign-in-button'
                    ]
                    
                    signed_in = False
                    for selector in sign_in_selectors:
                        try:
                            sign_button = page.locator(selector).first
                            if sign_button.is_visible(timeout=1000):
                                sign_button.click()
                                print(f"[+] 执行了签到操作")
                                signed_in = True
                                break
                        except:
                            continue
                    
                    if not signed_in:
                        print(f"[*] 未找到明显的签到按钮，可能已自动签到或无需手动签到")
                    
                    # 签到后获取余额信息
                    time.sleep(1)
                    balance_info = get_balance_info(page)
                    if balance_info:
                        print(f"💰 余额信息: {balance_info}")
                        
                except Exception as e:
                    print(f"[*] 签到检测过程中出现异常: {e}")
                
            else:
                print(f"[!] 未能确认登录状态，当前URL: {current_url}")
            
            browser.close()
            print(f"[✓] 账号 {account['username']} 处理完成")
            return {'success': True, 'balance_info': balance_info}
            
    except Exception as e:
        print(f"[!] 账号 {account['username']} 处理失败: {e}")
        try:
            if 'browser' in locals():
                browser.close()
        except:
            pass
        return {'success': False, 'balance_info': None}

def main(send_notification=True):
    """主程序
    
    Args:
        send_notification: 是否发送Telegram通知
    """
    print("=" * 70)
    print("Optimized Auto Login Script (with balance display)")
    print("=" * 70)
    
    success_count = 0
    total_count = len(accounts)
    account_results = []  # 存储每个账号的结果
    
    start_time = time.time()
    
    for i, account in enumerate(accounts):
        print(f"\n📋 处理账号 {i+1}/{total_count}: {account['username']}")
        
        account_start_time = time.time()
        result = optimized_login_and_sign(account)
        account_end_time = time.time()
        
        # 处理新的返回格式
        success = result['success'] if isinstance(result, dict) else result
        balance_info = result.get('balance_info') if isinstance(result, dict) else None
        
        account_result = {
            'username': account['username'],
            'success': success,
            'duration': account_end_time - account_start_time,
            'balance_info': balance_info
        }
        account_results.append(account_result)
        
        if success:
            success_count += 1
            print(f"✅ 成功 (耗时: {account_end_time - account_start_time:.1f}秒)")
        else:
            print(f"❌ 失败 (耗时: {account_end_time - account_start_time:.1f}秒)")
        
        # 账号间随机延迟，避免被检测
        if i < total_count - 1:
            delay = random.randint(1, 3)
            print(f"⏰ 等待 {delay} 秒后处理下一个账号...")
            time.sleep(delay)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print("\n" + "=" * 70)
    print("📊 处理结果统计")
    print("=" * 70)
    print(f"✅ 成功: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")
    print(f"❌ 失败: {total_count - success_count}/{total_count}")
    print(f"⏱️  总耗时: {total_time:.1f} 秒")
    print(f"📈 平均每账号: {total_time/total_count:.1f} 秒")
    
    # 显示账号详细信息
    print(f"\n💰 账号余额概览:")
    print("-" * 70)
    for result in account_results:
        username_short = result['username'].split('@')[0]  # 只显示用户名部分
        status = "✅ 登录成功" if result['success'] else "❌ 登录失败"
        duration = f"⏱️ {result['duration']:.1f}s"
        
        if result['success'] and result['balance_info']:
            # 显示详细余额信息
            print(f"📧 {username_short:20} | {status} | {duration}")
            print(f"   {result['balance_info']}")
        else:
            # 只显示基本信息
            print(f"📧 {username_short:20} | {status} | {duration}")
            if not result['success']:
                print(f"   ❌ 无法获取余额信息")
    
    print("=" * 70)
    
    # 发送Telegram通知
    if send_notification:
        try:
            from telegram_notify import TelegramNotifier
            notifier = TelegramNotifier()
            if notifier.is_configured():
                # 准备通知数据
                notification_results = []
                for result in account_results:
                    notification_results.append({
                        'account': result['username'],
                        'success': result['success'],
                        'status': '登录成功' if result['success'] else '登录失败',
                        'balance_info': result.get('balance_info', ''),
                        'message': ''
                    })
                notifier.send_anyrouter_result(notification_results)
        except Exception as e:
            print(f"发送Telegram通知失败: {e}")
    
    return account_results  # 返回结果供其他脚本使用

if __name__ == '__main__':
    main()
