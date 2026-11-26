package com.autoaccount;

/**
 * Bridge from the Java capture services into the running Python/Kivy app.
 *
 * <p>The accessibility service and the notification listener both run in the
 * app's own process, so a direct static call is the fastest and most reliable
 * delivery path. The broadcast intent is kept as a secondary path (e.g. when
 * the Python activity is not alive yet).</p>
 */
public class PythonCallbackHandler {

    public interface TransactionCallback {
        void onTransactionDetected(double amount, String type, String merchant,
                                   String category, String packageName,
                                   String rawText, long timestamp, String channel);
    }

    private static TransactionCallback callback;

    public static void setCallback(TransactionCallback cb) {
        callback = cb;
    }

    public static void clearCallback() {
        callback = null;
    }

    static void deliver(TransactionParser.TransactionInfo info) {
        TransactionCallback cb = callback;
        if (cb == null) {
            return;
        }
        try {
            cb.onTransactionDetected(
                    info.amount,
                    info.type,
                    info.merchant != null ? info.merchant : "",
                    info.category,
                    info.packageName,
                    info.rawText,
                    info.timestamp,
                    info.channel);
        } catch (Exception ignored) {
            // Python side may be shutting down; the broadcast covers that case.
        }
    }
}
