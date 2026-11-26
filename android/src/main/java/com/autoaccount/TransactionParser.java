package com.autoaccount;

import android.content.Context;
import android.content.Intent;
import android.util.Log;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Shared parsing for payment screens (accessibility) and payment notifications.
 * Kept in one place so both capture channels behave identically.
 */
public final class TransactionParser {

    private static final String TAG = "AutoAccountParser";

    public static final String ACTION_DETECTED = "com.autoaccount.TRANSACTION_DETECTED";

    /** Apps whose payment / income pages we watch. */
    public static final String[] TARGET_PACKAGES = {
            "com.eg.android.AlipayGphone",   // 支付宝
            "com.tencent.mm",                // 微信
            "com.alibaba.android.rimet",     // 钉钉
            "com.tencent.mobileqq",          // QQ
            "com.chinamworld.bocmbci",       // 中国银行
            "com.icbc.banking",              // 工商银行
            "com.cmbc.personalbanking",      // 招商银行
            "com.abchina.mobilebank",        // 农业银行
            "com.bankcomm.BankComm",         // 交通银行
            "com.unionpay.uppay",            // 云闪付
            "com.jd.mobile",                 // 京东金融
            "com.taobao.taobao",             // 淘宝
            "com.xunmeng.pinduoduo",         // 拼多多
    };

    private static final String[] EXPENSE_KEYWORDS = {
            "支付", "付款", "消费", "扣款", "转出", "发红包", "充值", "缴费", "支出", "已支付"
    };

    private static final String[] INCOME_KEYWORDS = {
            "收款", "转入", "收到", "红包收入", "退款", "工资", "到账", "收入", "入账", "已到账"
    };

    private static final Pattern[] AMOUNT_PATTERNS = {
            Pattern.compile("[¥￥]\\s*(\\d{1,3}(?:,\\d{3})*(?:\\.\\d{1,2})?)"),
            Pattern.compile("(\\d{1,3}(?:,\\d{3})*(?:\\.\\d{1,2})?)\\s*元"),
            Pattern.compile("金额[：:]\\s*[¥￥]?\\s*(\\d+(?:\\.\\d{1,2})?)"),
            Pattern.compile("支付[：:]\\s*[¥￥]?\\s*(\\d+(?:\\.\\d{1,2})?)"),
            Pattern.compile("收款[：:]\\s*[¥￥]?\\s*(\\d+(?:\\.\\d{1,2})?)"),
            Pattern.compile("转账[：:]\\s*[¥￥]?\\s*(\\d+(?:\\.\\d{1,2})?)"),
            Pattern.compile("(\\d+(?:\\.\\d{1,2})?)\\s*[元￥¥]"),
    };

    private static final String[] NOISE_TOKENS = {
            "支付", "付款", "收款", "转账", "消费", "扣款", "充值", "缴费",
            "成功", "完成", "订单", "订单号", "金额", "元", "余额", "详情", "账单",
            "支出", "收入", "来自", "给", "向", "共", "笔", "已支付", "已到账",
            "微信支付", "支付宝", "微信", "云闪付", "通知", "提醒"
    };

    private static final String[] APP_NAMES = {
            "支付宝", "微信", "微信支付", "云闪付", "钉钉", "QQ", "手机银行",
            "中国银行", "工商银行", "招商银行", "建设银行", "农业银行", "交通银行"
    };

    private static final String[][] CATEGORY_KEYWORDS = {
            {"food", new String[]{"餐", "饭", "吃", "外卖", "美团", "饿了么", "肯德基", "麦当劳",
                    "星巴克", "咖啡", "奶茶", "食堂", "烧烤", "火锅"}},
            {"transport", new String[]{"打车", "滴滴", "高德", "地铁", "公交", "火车", "飞机",
                    "机票", "加油", "停车", "高速"}},
            {"shopping", new String[]{"淘宝", "京东", "拼多多", "购物", "超市", "便利店",
                    "商场", "天猫", "唯品会", "盒马"}},
            {"entertainment", new String[]{"电影", "游戏", "网易云", "QQ音乐", "爱奇艺",
                    "腾讯视频", "B站", "哔哩哔哩", "会员", "KTV"}},
            {"medical", new String[]{"医院", "药店", "挂号", "体检", "买药", "药房", "诊所"}},
            {"housing", new String[]{"房租", "水费", "电费", "燃气费", "物业费", "宽带", "网费"}},
            {"communication", new String[]{"话费", "流量", "移动", "联通", "电信", "充话费"}},
    };

    private TransactionParser() {
    }

    /** Result of parsing one screen / notification. */
    public static class TransactionInfo {
        public final double amount;
        public final String type;        // "expense" | "income"
        public final String merchant;
        public final String category;    // english key, mapped to a category on the Python side
        public final String packageName;
        public final String rawText;
        public final long timestamp;
        public final String channel;     // "accessibility" | "notification"

        TransactionInfo(double amount, String type, String merchant, String category,
                        String packageName, String rawText, long timestamp, String channel) {
            this.amount = amount;
            this.type = type;
            this.merchant = merchant;
            this.category = category;
            this.packageName = packageName;
            this.rawText = rawText;
            this.timestamp = timestamp;
            this.channel = channel;
        }
    }

    public static TransactionInfo parse(String text, String packageName, String channel) {
        if (text == null || text.isEmpty()) {
            return null;
        }

        Double amount = null;
        for (Pattern pattern : AMOUNT_PATTERNS) {
            Matcher matcher = pattern.matcher(text);
            if (matcher.find()) {
                String raw = matcher.group(1).replace(",", "");
                try {
                    double value = Double.parseDouble(raw);
                    if (value > 0) {
                        amount = value;
                        break;
                    }
                } catch (NumberFormatException ignored) {
                    // try the next pattern
                }
            }
        }
        if (amount == null) {
            return null;
        }

        String type = null;
        for (String kw : EXPENSE_KEYWORDS) {
            if (text.contains(kw)) {
                type = "expense";
                break;
            }
        }
        if (type == null) {
            for (String kw : INCOME_KEYWORDS) {
                if (text.contains(kw)) {
                    type = "income";
                    break;
                }
            }
        }
        if (type == null) {
            return null;
        }

        return new TransactionInfo(
                amount, type,
                extractMerchant(text),
                detectCategory(text),
                packageName,
                text.length() > 500 ? text.substring(0, 500) : text,
                System.currentTimeMillis(),
                channel);
    }

    private static String extractMerchant(String text) {
        String[] patterns = {
                "商户[：:]\\s*([^\\n\\r]+)",
                "收款方[：:]\\s*([^\\n\\r]+)",
                "付款方[：:]\\s*([^\\n\\r]+)",
                "对方[：:]\\s*([^\\n\\r]+)",
                "来自[：:]?\\s*([^\\s，,。]+)",
        };
        for (String pattern : patterns) {
            Matcher matcher = Pattern.compile(pattern).matcher(text);
            if (matcher.find()) {
                String value = matcher.group(1).trim();
                if (!value.isEmpty()) {
                    return value;
                }
            }
        }

        String[] parts = text.split("[\\s，,。:：]+");
        for (String part : parts) {
            if (isMerchantLike(part)) {
                return part;
            }
        }
        return null;
    }

    private static boolean isMerchantLike(String token) {
        if (token == null || token.isEmpty()) {
            return false;
        }
        for (String noise : NOISE_TOKENS) {
            if (noise.equals(token)) {
                return false;
            }
        }
        for (String app : APP_NAMES) {
            if (app.equals(token)) {
                return false;
            }
        }
        if (token.matches(".*\\d.*")) {
            return false;
        }
        return token.length() >= 2;
    }

    private static String detectCategory(String text) {
        for (String[] entry : CATEGORY_KEYWORDS) {
            for (String kw : entry[1]) {
                if (text.contains(kw)) {
                    return entry[0];
                }
            }
        }
        return "other";
    }

    /** Broadcast a parsed transaction to the Python layer. */
    public static void dispatch(Context context, TransactionInfo info) {
        if (info == null) {
            return;
        }
        Intent intent = new Intent(ACTION_DETECTED);
        intent.setPackage(context.getPackageName());
        intent.putExtra("amount", info.amount);
        intent.putExtra("type", info.type);
        intent.putExtra("merchant", info.merchant != null ? info.merchant : "");
        intent.putExtra("category", info.category);
        intent.putExtra("package", info.packageName);
        intent.putExtra("raw_text", info.rawText);
        intent.putExtra("timestamp", info.timestamp);
        intent.putExtra("channel", info.channel);

        // In-process delivery: the app registers a receiver while running.
        PythonCallbackHandler.deliver(info);
        context.sendBroadcast(intent);
        Log.d(TAG, "detected " + info.type + " " + info.amount + " via " + info.channel);
    }
}
