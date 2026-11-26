package com.autoaccount;

import android.app.Notification;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.util.Log;

/**
 * Primary capture channel for WeChat / Alipay.
 *
 * <p>Payment apps push a plain-text notification after a payment
 * ("微信支付 · 支付成功 ¥25.00"). Reading notifications is far more reliable
 * than scraping the success screen, whose amount is often drawn as an image.</p>
 */
public class AutoAccountNotificationService extends NotificationListenerService {

    private static final String TAG = "AutoAccountNotif";

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (sbn == null || sbn.getNotification() == null) {
            return;
        }
        String packageName = sbn.getPackageName();
        if (!isTarget(packageName)) {
            return;
        }

        Bundle extras = sbn.getNotification().extras;
        if (extras == null) {
            return;
        }

        StringBuilder builder = new StringBuilder();
        append(builder, extras.getCharSequence(Notification.EXTRA_TITLE));
        append(builder, extras.getCharSequence(Notification.EXTRA_TEXT));
        append(builder, extras.getCharSequence(Notification.EXTRA_BIG_TEXT));
        append(builder, extras.getCharSequence(Notification.EXTRA_SUB_TEXT));

        String text = builder.toString().trim();
        if (text.isEmpty()) {
            return;
        }

        TransactionParser.TransactionInfo info =
                TransactionParser.parse(text, packageName, "notification");
        if (info != null) {
            TransactionParser.dispatch(this, info);
        }
    }

    private void append(StringBuilder builder, CharSequence value) {
        if (value == null) {
            return;
        }
        String text = value.toString().trim();
        if (text.isEmpty()) {
            return;
        }
        if (builder.indexOf(text) >= 0) {
            return;
        }
        if (builder.length() > 0) {
            builder.append(' ');
        }
        builder.append(text);
    }

    private boolean isTarget(String packageName) {
        for (String target : TransactionParser.TARGET_PACKAGES) {
            if (target.equals(packageName)) {
                return true;
            }
        }
        return false;
    }

    @Override
    public void onListenerConnected() {
        super.onListenerConnected();
        Log.d(TAG, "notification listener connected");
    }
}
