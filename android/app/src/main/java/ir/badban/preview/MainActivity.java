package ir.badban.preview;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
    // The APK displays the existing read-only Render preview; it does not expose backend access.
    private static final Uri PREVIEW_URL =
            Uri.parse("https://badban-ui-preview.onrender.com/");
    private WebView webView;
    private TextView status;

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        WebView.setWebContentsDebuggingEnabled(false);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        layout.setBackgroundColor(Color.WHITE);

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(12), dp(7), dp(12), dp(7));
        toolbar.setBackgroundColor(Color.rgb(7, 25, 52));

        status = new TextView(this);
        status.setText(R.string.preview_status);
        status.setTextColor(Color.WHITE);
        status.setTextSize(12);
        toolbar.addView(status, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        Button home = toolbarButton(getString(R.string.button_home));
        home.setOnClickListener(v -> webView.loadUrl(PREVIEW_URL.toString()));
        toolbar.addView(home);

        Button refresh = toolbarButton(getString(R.string.button_refresh));
        refresh.setOnClickListener(v -> webView.reload());
        toolbar.addView(refresh);

        layout.addView(toolbar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        webView = new WebView(this);
        configureWebView();
        layout.addView(webView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(layout);
        webView.loadUrl(PREVIEW_URL.toString());
    }

    private Button toolbarButton(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setTextSize(11);
        button.setAllCaps(false);
        button.setTextColor(Color.rgb(7, 25, 52));
        return button;
    }

    private int dp(int pixels) {
        return Math.round(pixels * getResources().getDisplayMetrics().density);
    }

    private static boolean isPreviewPage(Uri uri) {
        return "https".equalsIgnoreCase(uri.getScheme())
                && "badban-ui-preview.onrender.com".equalsIgnoreCase(uri.getHost())
                && (uri.getPath() == null || "/".equals(uri.getPath()));
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        // JS and DOM storage are required for the React SPA, not for native auth.
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setGeolocationEnabled(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            settings.setSafeBrowsingEnabled(true);
        }
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame()) {
                    return false;
                }
                Uri url = request.getUrl();
                if (isPreviewPage(url)) {
                    return false;
                }
                // Leave the wrapper for external links; never silently navigate to auth/API pages.
                if ("https".equalsIgnoreCase(url.getScheme())) {
                    startActivity(new Intent(Intent.ACTION_VIEW, url));
                }
                return true;
            }

            @Override
            public void onPageStarted(WebView view, String url,
                                      android.graphics.Bitmap favicon) {
                status.setText(R.string.loading_status);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                status.setText(R.string.preview_status);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                if (request.isForMainFrame()) {
                    status.setText(R.string.offline_status);
                }
            }

            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel();
                status.setText(R.string.offline_status);
            }
        });
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}
