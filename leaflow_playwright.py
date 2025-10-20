#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LeafFlow 自动签到脚本 - Playwright版本
从Selenium迁移到Playwright，提供更好的性能和稳定性
"""

import time
import random
import re
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright

class LeafFlowAutoCheckin:
    def __init__(self):
        """初始化"""
        self.setup_logging()
        self.results = []
        self.start_time = datetime.now()
        
    def setup_logging(self):
        """设置日志 - 仅控制台输出"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()  # 只保留控制台输出
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def read_accounts(self):
        """读取账号列表"""
        try:
            with open('leaflow-account.txt', 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            accounts = []
            for line in lines:
                line = line.strip()
                if line and ',' in line:
                    email, password = line.split(',', 1)
                    accounts.append({
                        'email': email.strip(),
                        'password': password.strip()
                    })
            
            self.logger.info(f"成功读取 {len(accounts)} 个账号")
            return accounts
        except Exception as e:
            self.logger.error(f"读取账号失败: {str(e)}")
            return []
    
    def extract_amount(self, text):
        """从文本中提取金额"""
        pattern = r'(\d+\.?\d*)\s*元'
        matches = re.findall(pattern, text)
        
        for match in matches:
            amount = float(match)
            if 0.01 <= amount <= 10:  # 合理的奖励范围
                return amount
        return 0.0
    
    def handle_popup(self, page):
        """处理弹窗"""
        try:
            # 方法1: 点击"稍后再说"按钮
            later_btn = page.locator("button:has-text('稍后再说')")
            if later_btn.is_visible(timeout=1000):
                later_btn.click()
                self.logger.debug("关闭弹窗：稍后再说")
                return True
        except:
            pass
        
        try:
            # 方法2: 按ESC键关闭弹窗
            page.keyboard.press('Escape')
            self.logger.debug("关闭弹窗：ESC键")
            return True
        except:
            pass
        
        return False
    
    def click_checkin_button(self, page):
        """点击签到按钮的多种方法"""
        self.logger.info("尝试点击签到按钮...")
        
        # 方法1: 通过文本查找签到按钮
        try:
            self.logger.info("方法1: 通过文本查找按钮")
            # 查找包含"签到"但不包含"已"的按钮
            sign_btn = page.locator("button:has-text('签到')").filter(has_not_text="已")
            if sign_btn.count() > 0:
                sign_btn.first.click()
                self.logger.info("✅ 成功点击签到按钮（文本匹配）")
                return True
        except Exception as e:
            self.logger.debug(f"方法1失败: {str(e)}")
        
        # 方法2: 通过JavaScript执行点击
        try:
            self.logger.info("方法2: JavaScript点击")
            result = page.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    for (let button of buttons) {
                        if (button.textContent.includes('签到') && 
                            !button.textContent.includes('已') &&
                            !button.disabled) {
                            button.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if result:
                self.logger.info("✅ 成功点击签到按钮（JavaScript）")
                return True
        except Exception as e:
            self.logger.debug(f"方法2失败: {str(e)}")
        
        # 方法3: 通过图标或特殊标记查找
        try:
            self.logger.info("方法3: 查找可点击的签到元素")
            # 尝试多个可能的选择器
            selectors = [
                "button:not([disabled]):has-text('立即签到')",
                "button:not([disabled]):has-text('签到')",
                "[onclick*='checkin']",
                "[onclick*='sign']",
                ".checkin-button",
                ".sign-button"
            ]
            
            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    if element.is_visible(timeout=500):
                        element.click()
                        self.logger.info(f"✅ 成功点击签到按钮（选择器: {selector}）")
                        return True
                except:
                    continue
                    
        except Exception as e:
            self.logger.debug(f"方法3失败: {str(e)}")
        
        self.logger.error("❌ 所有点击方法都失败了")
        return False
    
    def process_account(self, browser, account):
        """处理单个账号"""
        email = account['email']
        password = account['password']
        
        result = {
            'email': email,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': '',
            'amount': 0.0,
            'message': '',
            'success': False
        }
        
        # 创建新的浏览器上下文和页面
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.set_default_timeout(10000)  # 10秒超时
        
        try:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"处理账号: {email}")
            self.logger.info(f"{'='*60}")
            
            # 1. 访问登录页面
            self.logger.info("步骤1: 访问登录页面...")
            page.goto("https://leaflow.net/login", wait_until='domcontentloaded')
            time.sleep(2)
            
            # 2. 处理弹窗
            self.logger.info("步骤2: 处理弹窗...")
            self.handle_popup(page)
            
            # 3. 输入邮箱
            self.logger.info("步骤3: 输入邮箱...")
            email_input = page.locator("input[type='email'], input[placeholder*='邮箱']").first
            email_input.fill(email)
            time.sleep(0.5)
            
            # 4. 触发密码框（如果需要）
            self.logger.info("步骤4: 触发密码框...")
            try:
                submit_btn = page.locator("button[type='submit']").first
                if submit_btn.is_visible():
                    submit_btn.click()
                    time.sleep(1)
            except:
                pass
            
            # 5. 输入密码
            self.logger.info("步骤5: 输入密码...")
            password_input = page.locator("input[type='password']").first
            password_input.fill(password)
            time.sleep(0.5)
            
            # 6. 提交登录
            self.logger.info("步骤6: 提交登录...")
            password_input.press('Enter')
            
            # 等待页面跳转
            try:
                page.wait_for_url('**/dashboard**', timeout=5000)
                self.logger.info("✅ 登录成功")
            except:
                try:
                    page.wait_for_url('**/home**', timeout=3000)
                    self.logger.info("✅ 登录成功")
                except:
                    # 检查是否仍在登录页
                    if 'login' in page.url:
                        result['status'] = '登录失败'
                        result['message'] = '账号或密码错误'
                        self.logger.error(f"❌ 登录失败")
                        return result
            
            # 7. 再次处理弹窗
            self.logger.info("步骤7: 再次处理弹窗...")
            self.handle_popup(page)
            time.sleep(1)
            
            # 8. 访问签到页面
            self.logger.info("步骤8: 访问签到页面...")
            page.goto("https://checkin.leaflow.net", wait_until='domcontentloaded')
            time.sleep(2)
            
            # 9. 分析页面状态
            self.logger.info("步骤9: 分析页面状态...")
            page_content = page.content()
            
            # 检查是否已签到
            if '今日已签到' in page_content or ('已签到' in page_content and '立即签到' not in page_content):
                amount = self.extract_amount(page_content)
                result['status'] = '今日已签到'
                result['amount'] = amount
                result['message'] = f'获得 {amount:.2f} 元' if amount > 0 else '已签到'
                result['success'] = True
                self.logger.info(f"✅ 今日已签到，获得 {amount:.2f} 元")
                return result
            
            # 10. 执行签到
            self.logger.info("步骤10: 执行签到...")
            
            # 尝试点击签到按钮
            if self.click_checkin_button(page):
                time.sleep(2)
                
                # 检查签到结果
                page_content = page.content()
                amount = self.extract_amount(page_content)
                
                if '签到成功' in page_content or '获得' in page_content or amount > 0:
                    result['status'] = '签到成功'
                    result['amount'] = amount
                    result['message'] = f'获得 {amount:.2f} 元'
                    result['success'] = True
                    self.logger.info(f"✅ 签到成功！获得 {amount:.2f} 元")
                elif '今日已签到' in page_content or '已签到' in page_content:
                    result['status'] = '签到成功（已确认）'
                    result['amount'] = amount
                    result['message'] = f'获得 {amount:.2f} 元' if amount > 0 else '签到成功'
                    result['success'] = True
                    self.logger.info(f"✅ 签到已完成")
                else:
                    result['status'] = '签到状态未知'
                    result['message'] = '未能确认签到结果'
                    self.logger.warning("⚠️ 签到状态未知")
            else:
                result['status'] = '签到失败'
                result['message'] = '无法点击签到按钮'
                self.logger.error("❌ 无法点击签到按钮")
                
        except Exception as e:
            result['status'] = '处理失败'
            result['message'] = str(e)
            self.logger.error(f"❌ 处理失败: {str(e)}")
        finally:
            # 关闭页面和上下文
            context.close()
        
        return result
    
    def save_results(self):
        """保存签到结果"""
        timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
        
        # 保存文本报告
        report_filename = f"checkin_report_{timestamp}.txt"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("LeafLow 自动签到报告 (Playwright版)\n")
            f.write(f"执行时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            
            success_count = sum(1 for r in self.results if r['success'])
            total_amount = sum(r['amount'] for r in self.results)
            
            f.write(f"📊 统计信息\n")
            f.write(f"总账号数: {len(self.results)}\n")
            f.write(f"成功数量: {success_count}\n")
            f.write(f"失败数量: {len(self.results) - success_count}\n")
            f.write(f"成功率: {success_count/len(self.results)*100:.1f}%\n")
            f.write(f"💰 总获得金额: {total_amount:.2f} 元\n\n")
            
            f.write("📋 详细结果:\n")
            f.write("-" * 60 + "\n")
            
            for i, r in enumerate(self.results, 1):
                status_icon = "✅" if r['success'] else "❌"
                f.write(f"\n{i}. {status_icon} {r['email']}\n")
                f.write(f"   状态: {r['status']}\n")
                if r['amount'] > 0:
                    f.write(f"   金额: {r['amount']:.2f} 元\n")
                if r['message']:
                    f.write(f"   备注: {r['message']}\n")
                f.write(f"   时间: {r['time']}\n")
            
            f.write("\n" + "=" * 60 + "\n")
        
        self.logger.info(f"文本报告已保存: {report_filename}")
    
    def run(self, send_notification=True):
        """运行主流程"""
        self.logger.info("=" * 80)
        self.logger.info("🚀 LeafLow 自动签到脚本 (Playwright版)")
        self.logger.info(f"⏰ 开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 80)
        
        # 读取账号
        accounts = self.read_accounts()
        if not accounts:
            self.logger.error("没有找到有效账号")
            return
        
        # 启动Playwright
        with sync_playwright() as p:
            # 启动浏览器（无头模式）
            browser = p.chromium.launch(
                headless=True,  # 设置为False可以看到浏览器窗口
                channel="chrome",  # 使用系统Chrome
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--no-first-run',
                    '--disable-default-apps'
                ]
            )
            
            # 处理每个账号
            for i, account in enumerate(accounts, 1):
                self.logger.info(f"\n[{i}/{len(accounts)}] 开始处理第{i}个账号...")
                
                try:
                    result = self.process_account(browser, account)
                    self.results.append(result)
                except Exception as e:
                    self.logger.error(f"处理账号时发生异常: {str(e)}")
                    self.results.append({
                        'email': account['email'],
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'status': '异常',
                        'amount': 0.0,
                        'message': str(e),
                        'success': False
                    })
                
                # 账号间延迟
                if i < len(accounts):
                    delay = random.randint(1, 3)
                    self.logger.info(f"等待 {delay} 秒后处理下一个账号...")
                    time.sleep(delay)
            
            # 关闭浏览器
            browser.close()
        
        # 打印总结
        self.logger.info("\n" + "=" * 80)
        self.logger.info("📊 签到完成 - 最终结果")
        self.logger.info("=" * 80)
        
        success_count = sum(1 for r in self.results if r['success'])
        total_amount = sum(r['amount'] for r in self.results)
        
        self.logger.info(f"总账号数: {len(self.results)}")
        self.logger.info(f"成功数量: {success_count}")
        self.logger.info(f"失败数量: {len(self.results) - success_count}")
        if len(self.results) > 0:
            self.logger.info(f"成功率: {success_count/len(self.results)*100:.1f}%")
        self.logger.info(f"💰 总获得金额: {total_amount:.2f} 元")
        
        self.logger.info("\n📋 账号明细:")
        for i, r in enumerate(self.results, 1):
            status = "✅" if r['success'] else "❌"
            amount_str = f" - {r['amount']:.2f}元" if r['amount'] > 0 else ""
            self.logger.info(f"{i}. {status} {r['email']}: {r['status']}{amount_str}")
        
        # 保存结果
        self.save_results()
        
        self.logger.info("\n" + "=" * 80)
        self.logger.info("✅ 所有任务已完成！")
        self.logger.info(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 80)
        
        # 发送Telegram通知
        if send_notification:
            try:
                from telegram_notify import TelegramNotifier
                notifier = TelegramNotifier()
                if notifier.is_configured():
                    notifier.send_leaflow_result(self.results)
            except Exception as e:
                print(f"发送Telegram通知失败: {e}")
        
        return self.results  # 返回结果供其他脚本使用

def main(send_notification=True):
    """主函数
    
    Args:
        send_notification: 是否发送Telegram通知
    """
    try:
        checkin = LeafFlowAutoCheckin()
        return checkin.run(send_notification)
    except KeyboardInterrupt:
        print("\n\n⏸️ 用户中断执行")
        return []
    except Exception as e:
        print(f"\n\n❌ 程序异常: {str(e)}")
        return []

if __name__ == "__main__":
    main()
