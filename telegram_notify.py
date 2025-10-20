#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram 电报通知模块
用于发送签到结果到 Telegram
"""

import requests
import os
from datetime import datetime

class TelegramNotifier:
    def __init__(self, bot_token=None, chat_id=None):
        """
        初始化 Telegram 通知器
        
        Args:
            bot_token: Telegram Bot Token (可从环境变量读取)
            chat_id: Telegram Chat ID (可从环境变量读取)
        """
        self.bot_token = bot_token or os.environ.get('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.environ.get('TELEGRAM_CHAT_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
    def is_configured(self):
        """检查是否配置了 Telegram"""
        return bool(self.bot_token and self.chat_id)
    
    def send_message(self, message, parse_mode='HTML'):
        """
        发送消息到 Telegram
        
        Args:
            message: 要发送的消息内容
            parse_mode: 消息格式 ('HTML' 或 'Markdown')
        
        Returns:
            bool: 发送是否成功
        """
        if not self.is_configured():
            print("⚠️ Telegram 未配置，跳过通知")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                print("✅ Telegram 通知发送成功")
                return True
            else:
                print(f"❌ Telegram 通知失败: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 发送 Telegram 通知时出错: {e}")
            return False
    
    def format_checkin_result(self, site_name, results):
        """
        格式化签到结果为 Telegram 消息
        
        Args:
            site_name: 网站名称
            results: 签到结果列表
        
        Returns:
            str: 格式化后的消息
        """
        time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 统计信息
        total = len(results)
        success = sum(1 for r in results if r.get('success', False))
        failed = total - success
        
        # 构建消息
        message = f"<b>🤖 {site_name} 自动签到报告</b>\n"
        message += f"⏰ 时间: {time_str}\n"
        message += f"━━━━━━━━━━━━━━━━\n"
        message += f"📊 <b>统计信息</b>\n"
        message += f"• 总账号: {total}\n"
        message += f"• ✅ 成功: {success}\n"
        message += f"• ❌ 失败: {failed}\n"
        
        if total > 0:
            success_rate = (success / total) * 100
            message += f"• 📈 成功率: {success_rate:.1f}%\n"
        
        # 详细结果
        message += f"\n<b>📋 详细结果</b>\n"
        for i, result in enumerate(results, 1):
            # 获取账号信息（隐藏部分）
            account = result.get('account', result.get('email', result.get('username', 'Unknown')))
            if '@' in account:
                # 隐藏邮箱部分内容
                parts = account.split('@')
                if len(parts[0]) > 3:
                    account = parts[0][:3] + '***@' + parts[1]
            
            # 状态图标
            status_icon = "✅" if result.get('success', False) else "❌"
            
            # 构建每个账号的结果
            message += f"\n{i}. {status_icon} <code>{account}</code>\n"
            
            # 添加状态信息
            status = result.get('status', '未知')
            message += f"   状态: {status}\n"
            
            # 添加余额信息（如果有）
            if 'balance_info' in result and result['balance_info']:
                message += f"   💰 {result['balance_info']}\n"
            elif 'amount' in result and result['amount'] > 0:
                message += f"   💰 获得: {result['amount']:.2f} 元\n"
            
            # 添加消息（如果有）
            if 'message' in result and result['message']:
                message += f"   📝 {result['message']}\n"
        
        message += f"\n━━━━━━━━━━━━━━━━"
        
        return message
    
    def send_anyrouter_result(self, results):
        """发送 AnyRouter 签到结果"""
        message = self.format_checkin_result("AnyRouter", results)
        return self.send_message(message)
    
    def send_leaflow_result(self, results):
        """发送 LeafFlow 签到结果"""
        message = self.format_checkin_result("LeafFlow", results)
        return self.send_message(message)
    
    def send_summary(self, all_results):
        """
        发送所有网站的签到总结
        
        Args:
            all_results: 包含所有网站结果的字典
        """
        time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        message = f"<b>🎯 每日签到总结</b>\n"
        message += f"⏰ {time_str}\n"
        message += f"━━━━━━━━━━━━━━━━\n\n"
        
        total_accounts = 0
        total_success = 0
        
        for site, results in all_results.items():
            if results:
                count = len(results)
                success = sum(1 for r in results if r.get('success', False))
                total_accounts += count
                total_success += success
                
                icon = "✅" if success == count else "⚠️" if success > 0 else "❌"
                message += f"{icon} <b>{site}</b>: {success}/{count}\n"
        
        if total_accounts > 0:
            message += f"\n<b>📊 总计</b>\n"
            message += f"• 账号总数: {total_accounts}\n"
            message += f"• 成功总数: {total_success}\n"
            message += f"• 总成功率: {(total_success/total_accounts*100):.1f}%\n"
        
        message += f"\n━━━━━━━━━━━━━━━━"
        
        return self.send_message(message)
    
    def send_error(self, error_message):
        """发送错误通知"""
        message = f"<b>⚠️ 签到脚本错误</b>\n\n"
        message += f"<code>{error_message}</code>\n"
        message += f"\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return self.send_message(message)

# 测试函数
def test_telegram():
    """测试 Telegram 通知"""
    notifier = TelegramNotifier()
    
    if not notifier.is_configured():
        print("请设置环境变量:")
        print("  TELEGRAM_BOT_TOKEN: 你的 Bot Token")
        print("  TELEGRAM_CHAT_ID: 你的 Chat ID")
        print("\n获取方法:")
        print("1. 在 Telegram 中找 @BotFather 创建 Bot，获取 Token")
        print("2. 发送消息给你的 Bot")
        print("3. 访问 https://api.telegram.org/bot<TOKEN>/getUpdates 获取 Chat ID")
        return
    
    # 发送测试消息
    test_results = [
        {'account': 'test1@example.com', 'success': True, 'status': '签到成功', 'balance_info': '余额: $5.00'},
        {'account': 'test2@example.com', 'success': False, 'status': '登录失败', 'message': '密码错误'}
    ]
    
    notifier.send_anyrouter_result(test_results)

if __name__ == "__main__":
    test_telegram()
