package com.autoaccount;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public class TransactionBroadcastReceiver extends BroadcastReceiver {

    private static final String TAG = "TransactionReceiver";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        if ("com.autoaccount.TRANSACTION_DETECTED".equals(action)) {
            double amount = intent.getDoubleExtra("amount", 0);
            String type = intent.getStringExtra("type");
            String merchant = intent.getStringExtra("merchant");
            String category = intent.getStringExtra("category");
            String packageName = intent.getStringExtra("package");
            String rawText = intent.getStringExtra("raw_text");
            long timestamp = intent.getLongExtra("timestamp", 0);

            Log.d(TAG, "Received transaction: " + amount + " " + type + " from " + packageName);

            // Send to Python via callback
            if (PythonCallbackHandler.callback != null) {
                PythonCallbackHandler.callback.onTransactionDetected(
                    amount, type, merchant, category, packageName, rawText, timestamp
                );
            }
        }
    }
}