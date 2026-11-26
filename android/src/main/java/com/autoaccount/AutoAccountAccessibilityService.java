package com.autoaccount;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.ArrayList;
import java.util.List;

/**
 * Reads the visible text of payment screens (Alipay / WeChat / banking apps).
 *
 * <p>This channel is good for merchant names and categories, but some payment
 * success screens draw the amount as an image, which is why
 * {@link AutoAccountNotificationService} also exists.</p>
 */
public class AutoAccountAccessibilityService extends AccessibilityService {

    private static final String TAG = "AutoAccountA11y";
    private static final long DEBOUNCE_MS = 700;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private long lastEventTime = 0;
    private boolean isProcessing = false;
    private String lastSignature = "";

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        AccessibilityServiceInfo info = getServiceInfo();
        if (info == null) {
            info = new AccessibilityServiceInfo();
        }
        info.eventTypes = AccessibilityEvent.TYPES_ALL_MASK;
        info.packageNames = TransactionParser.TARGET_PACKAGES;
        info.feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC;
        info.notificationTimeout = 100;
        info.flags = AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS
                | AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
                | AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS;
        setServiceInfo(info);
        Log.d(TAG, "accessibility service connected");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event.getPackageName() == null) {
            return;
        }
        String packageName = event.getPackageName().toString();
        if (!isTarget(packageName)) {
            return;
        }

        long now = System.currentTimeMillis();
        if (now - lastEventTime < DEBOUNCE_MS) {
            return;
        }
        lastEventTime = now;

        handler.post(() -> processEvent(packageName));
    }

    private boolean isTarget(String packageName) {
        for (String target : TransactionParser.TARGET_PACKAGES) {
            if (target.equals(packageName)) {
                return true;
            }
        }
        return false;
    }

    private void processEvent(String packageName) {
        if (isProcessing) {
            return;
        }
        isProcessing = true;
        try {
            AccessibilityNodeInfo root = getRootInActiveWindow();
            if (root == null) {
                return;
            }
            String text = String.join(" ", collectText(root));
            if (text.length() < 8) {
                return;
            }

            // Deduplicate: the same screen fires many events.
            String signature = packageName + "|" + text.hashCode();
            if (signature.equals(lastSignature)) {
                return;
            }

            TransactionParser.TransactionInfo info =
                    TransactionParser.parse(text, packageName, "accessibility");
            if (info != null) {
                lastSignature = signature;
                TransactionParser.dispatch(this, info);
            }
        } finally {
            isProcessing = false;
        }
    }

    private List<String> collectText(AccessibilityNodeInfo node) {
        List<String> texts = new ArrayList<>();
        if (node == null) {
            return texts;
        }
        if (node.getText() != null) {
            String value = node.getText().toString().trim();
            if (!value.isEmpty()) {
                texts.add(value);
            }
        }
        if (node.getContentDescription() != null) {
            String value = node.getContentDescription().toString().trim();
            if (!value.isEmpty() && !texts.contains(value)) {
                texts.add(value);
            }
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            texts.addAll(collectText(node.getChild(i)));
        }
        return texts;
    }

    @Override
    public void onInterrupt() {
        Log.d(TAG, "accessibility service interrupted");
    }
}
