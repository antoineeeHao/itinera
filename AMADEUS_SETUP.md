# 获取真实Amadeus API凭证指南

## 步骤1: 注册Amadeus开发者账户

1. 访问: https://developers.amadeus.com/register
2. 填写注册信息（免费）
3. 验证邮箱

## 步骤2: 创建应用并获取凭证

1. 登录开发者控制台
2. 点击 "Create New App"
3. 填写应用信息：
   - App Name: ITINERA Flight Search
   - Description: Travel planning app with real-time flight prices
4. 获取你的凭证：
   - API Key (Client ID)
   - API Secret (Client Secret)

## 步骤3: 配置环境变量

1. 复制 .env.template 为 .env:
```bash
cp .env.template .env
```

2. 编辑 .env 文件，添加你的真实凭证:
```env
AMADEUS_API_KEY=your_real_api_key_here
AMADEUS_API_SECRET=your_real_api_secret_here
```

## 免费额度
- 每月1000次API调用
- 足够测试和小规模使用

## 测试步骤
配置完成后，重启应用，你将看到：
- ✅ "Real-time flight prices" - 使用真实API数据
- 具体航空公司信息
- 当前市场价格（24小时内更新）