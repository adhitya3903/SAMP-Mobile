package com.samp.mobile.game.ui;

import android.animation.ValueAnimator;
import android.app.Activity;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.DashPathEffect;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.LinearInterpolator;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.samp.mobile.R;

import java.util.Random;

/**
 * Loading screen Acropolize (tema futuristik hitam-biru-emas).
 *
 * Catatan: persen dan tahap adalah ESTIMASI animasi (client belum melaporkan progres asli),
 * bar akan melonjak ke 100% dan layar memudar saat game siap (hide() dipanggil dari native).
 */
public class LoadingScreen {

    // ====== BAGIAN YANG BOLEH KAMU EDIT ======
    private static final String[] TIPS = {
            "Gunakan waktu roleplay sebaik-baiknya dan jangan lupa beristirahat.",
            "Ketik /changelogs untuk melihat pembaruan terbaru server.",
            "Tekan tombol >> di sisi kiri layar untuk membuka panel tombol cepat seperti TAB dan ESC.",
            "Together We Are One \u2014 hormati sesama pemain dan nikmati ceritamu.",
            "Menemukan bug atau pelanggaran? Laporkan ke staff supaya cepat ditangani.",
            "Jaga karaktermu tetap realistis: ikuti aturan roleplay dan hindari metagaming.",
            "Untuk FPS yang lebih stabil, tutup aplikasi lain yang berjalan di latar belakang."
    };
    private static final String[] STAGES = {
            "Menyiapkan mesin game",
            "Memuat font dan tekstur",
            "Memuat model dan data dunia",
            "Menyiapkan dunia Los Santos",
            "Hampir selesai"
    };
    private static final float[] STAGE_AT = {0f, 0.12f, 0.35f, 0.62f, 0.85f};
    private static final String STAGE_DONE = "Siap!";
    private static final long TIP_INTERVAL_MS = 4500;
    private static final int GOLD = 0xFFFFD400;
    // =========================================

    private final Activity activity;
    private final float density;
    private final FrameLayout root;
    private final RingView ring;
    private final TextView percentText;
    private final TextView stageText;
    private final TextView tipText;
    private final View scanBand;
    private final View barFill;
    private final float scanTravel;
    private final ValueAnimator clock;

    private final long startTime = SystemClock.uptimeMillis();
    private long lastFrame = 0;
    private long lastTipSwitch = SystemClock.uptimeMillis();
    private int tipIndex;
    private int lastPercent = -1;
    private int lastStage = -1;
    private boolean hiding = false;

    public LoadingScreen(Activity activity) {
        this.activity = activity;
        DisplayMetrics dm = activity.getResources().getDisplayMetrics();
        this.density = dm.density;
        int shortSide = Math.min(dm.widthPixels, dm.heightPixels);
        int ringSize = Math.max(dp(110), Math.min(dp(200), Math.round(shortSide * 0.40f)));
        int bandH = dp(150);
        this.tipIndex = new Random().nextInt(TIPS.length);

        Typeface black = font(R.font.montserrat_black, Typeface.DEFAULT_BOLD);
        Typeface bold = font(R.font.montserrat_bold, Typeface.DEFAULT_BOLD);
        Typeface medium = font(R.font.montserrat_medium, Typeface.DEFAULT);

        root = new FrameLayout(activity);
        root.setBackgroundColor(0xFF05060A);
        root.setClickable(true); // jangan teruskan sentuhan ke game selama loading

        // Latar: gradien gelap + kilau + grid halus + vignette
        root.addView(new BackgroundView(activity, density), new FrameLayout.LayoutParams(-1, -1));

        // Garis pindai (scanline) yang bergerak pelan dari atas ke bawah
        scanBand = new View(activity);
        scanBand.setBackground(new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{0x00FFD400, 0x18FFD400, 0x00FFD400}));
        root.addView(scanBand, new FrameLayout.LayoutParams(-1, bandH));
        scanTravel = dm.heightPixels + bandH;
        scanBand.setTranslationY(-bandH);

        // Kolom utama: cincin progres + logo, judul, persen, tahap
        LinearLayout col = new LinearLayout(activity);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER_HORIZONTAL);
        FrameLayout.LayoutParams colP = new FrameLayout.LayoutParams(-2, -2, Gravity.CENTER);
        colP.bottomMargin = dp(52);
        root.addView(col, colP);

        FrameLayout ringFrame = new FrameLayout(activity);
        ring = new RingView(activity, density);
        ringFrame.addView(ring, new FrameLayout.LayoutParams(ringSize, ringSize));
        ImageView logo = new ImageView(activity);
        logo.setImageResource(R.drawable.logo);
        logo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        int logoSize = Math.round(ringSize * 0.56f);
        ringFrame.addView(logo, new FrameLayout.LayoutParams(logoSize, logoSize, Gravity.CENTER));
        col.addView(ringFrame, new LinearLayout.LayoutParams(ringSize, ringSize));

        TextView title = text("ACROPOLIZE", 22f, black, 0xFFFFFFFF, 0.22f);
        LinearLayout.LayoutParams titleP = new LinearLayout.LayoutParams(-2, -2);
        titleP.topMargin = dp(6);
        col.addView(title, titleP);

        col.addView(text("ROLEPLAY", 11f, bold, GOLD, 0.70f), new LinearLayout.LayoutParams(-2, -2));

        percentText = text("0%", 20f, bold, 0xFFFFFFFF, 0.04f);
        LinearLayout.LayoutParams pctP = new LinearLayout.LayoutParams(-2, -2);
        pctP.topMargin = dp(10);
        col.addView(percentText, pctP);

        stageText = text(STAGES[0], 11.5f, medium, 0x99FFFFFF, 0.06f);
        LinearLayout.LayoutParams stP = new LinearLayout.LayoutParams(-2, -2);
        stP.topMargin = dp(2);
        col.addView(stageText, stP);

        // Kartu tips di bawah
        LinearLayout tipCard = new LinearLayout(activity);
        tipCard.setOrientation(LinearLayout.HORIZONTAL);
        tipCard.setGravity(Gravity.CENTER_VERTICAL);
        GradientDrawable cardBg = new GradientDrawable();
        cardBg.setColor(0xB3101018);
        cardBg.setCornerRadius(dp(14));
        cardBg.setStroke(Math.max(1, dp(1)), 0x44FFD400);
        tipCard.setBackground(cardBg);
        tipCard.setPadding(dp(10), dp(9), dp(16), dp(9));

        TextView tag = text("TIPS", 10f, black, 0xFF111111, 0.15f);
        GradientDrawable tagBg = new GradientDrawable();
        tagBg.setColor(GOLD);
        tagBg.setCornerRadius(dp(8));
        tag.setBackground(tagBg);
        tag.setPadding(dp(9), dp(4), dp(9), dp(4));
        tipCard.addView(tag, new LinearLayout.LayoutParams(-2, -2));

        tipText = text(TIPS[tipIndex], 12.5f, medium, 0xEBFFFFFF, 0.01f);
        tipText.setGravity(Gravity.CENTER_VERTICAL | Gravity.START);
        tipText.setMinLines(2);
        tipText.setMaxLines(2);
        LinearLayout.LayoutParams tipP = new LinearLayout.LayoutParams(0, -2, 1f);
        tipP.leftMargin = dp(12);
        tipCard.addView(tipText, tipP);

        int cardW = Math.min(dm.widthPixels - dp(48), dp(560));
        FrameLayout.LayoutParams cardP = new FrameLayout.LayoutParams(cardW, -2,
                Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        cardP.bottomMargin = dp(24);
        root.addView(tipCard, cardP);

        // Info versi di pojok kanan atas
        TextView ver = text(versionLine(), 9.5f, medium, 0x73FFFFFF, 0.12f);
        FrameLayout.LayoutParams verP = new FrameLayout.LayoutParams(-2, -2, Gravity.TOP | Gravity.END);
        verP.topMargin = dp(16);
        verP.rightMargin = dp(20);
        root.addView(ver, verP);

        // Garis progres tipis di tepi bawah layar
        barFill = new View(activity);
        barFill.setBackground(new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT,
                new int[]{0xFFFFB800, 0xFFFFE14D}));
        root.addView(barFill, new FrameLayout.LayoutParams(-1, Math.max(2, dp(3)), Gravity.BOTTOM));
        barFill.setPivotX(0f);
        barFill.setScaleX(0f);

        activity.addContentView(root, new ViewGroup.LayoutParams(-1, -1));

        clock = ValueAnimator.ofFloat(0f, 1f);
        clock.setDuration(1000);
        clock.setRepeatCount(ValueAnimator.INFINITE);
        clock.setInterpolator(new LinearInterpolator());
        clock.addUpdateListener(a -> tick());
        clock.start();
    }

    /** Dipanggil saat game siap: lonjakkan ke 100% lalu pudar. */
    public void hide() {
        if (hiding) return;
        hiding = true;
        clock.cancel();
        ring.update(1f, 1f, 0f);
        barFill.setScaleX(1f);
        percentText.setText("100%");
        stageText.setText(STAGE_DONE);
        root.animate().alpha(0f).setStartDelay(280).setDuration(320)
                .withEndAction(() -> root.setVisibility(View.GONE)).start();
    }

    // ---------------------------------------------------------------- internal

    private void tick() {
        if (hiding) return;
        long now = SystemClock.uptimeMillis();
        if (now - lastFrame < 33) return; // ~30 FPS cukup, hemat CPU saat game dimuat
        lastFrame = now;
        long t = now - startTime;

        float progress = 0.94f * (1f - (float) Math.exp(-t / 16000.0));
        float pulse = 0.5f + 0.5f * (float) Math.sin(t / 2200.0 * 2.0 * Math.PI);
        float rotation = (t % 26000L) / 26000f * 360f;
        ring.update(progress, pulse, rotation);
        barFill.setScaleX(progress);
        scanBand.setTranslationY(-dp(150) + ((t % 3600L) / 3600f) * scanTravel);

        int pct = Math.round(progress * 100f);
        if (pct != lastPercent) {
            lastPercent = pct;
            percentText.setText(pct + "%");
        }
        int st = stageFor(progress);
        if (st != lastStage) {
            lastStage = st;
            stageText.setText(STAGES[st]);
        }
        if (now - lastTipSwitch > TIP_INTERVAL_MS) {
            lastTipSwitch = now;
            nextTip();
        }
    }

    private void nextTip() {
        tipText.animate().alpha(0f).setDuration(180).withEndAction(() -> {
            tipIndex = (tipIndex + 1) % TIPS.length;
            tipText.setText(TIPS[tipIndex]);
            tipText.animate().alpha(1f).setDuration(260).start();
        }).start();
    }

    private static int stageFor(float p) {
        int s = 0;
        for (int i = 0; i < STAGE_AT.length; i++) {
            if (p >= STAGE_AT[i]) s = i;
        }
        return s;
    }

    private int dp(float v) {
        return Math.round(v * density);
    }

    private Typeface font(int resId, Typeface fallback) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            try {
                Typeface t = activity.getResources().getFont(resId);
                if (t != null) return t;
            } catch (Throwable ignored) {
            }
        }
        return fallback;
    }

    private TextView text(String s, float sp, Typeface tf, int color, float spacing) {
        TextView t = new TextView(activity);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTypeface(tf);
        t.setTextColor(color);
        t.setLetterSpacing(spacing);
        t.setIncludeFontPadding(false);
        t.setGravity(Gravity.CENTER);
        return t;
    }

    private String versionLine() {
        String v = "";
        try {
            String name = activity.getPackageManager().getPackageInfo(activity.getPackageName(), 0).versionName;
            if (name != null) v = name;
        } catch (Exception ignored) {
        }
        String abi = (Build.SUPPORTED_ABIS != null && Build.SUPPORTED_ABIS.length > 0) ? Build.SUPPORTED_ABIS[0] : "";
        String s = "ACROPOLIZE CLIENT";
        if (!v.isEmpty()) s += "  \u2022  v" + v;
        if (!abi.isEmpty()) s += "  \u2022  " + abi;
        return s;
    }

    // ---------------------------------------------------------------- views

    /** Latar statis (digambar sekali, di-cache oleh GPU). */
    private static class BackgroundView extends View {
        private final float density;
        private final Paint base = new Paint();
        private final Paint glowGold = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint glowBlue = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint grid = new Paint();
        private final Paint vignette = new Paint();
        private float[] lines = new float[0];

        BackgroundView(Context ctx, float density) {
            super(ctx);
            this.density = density;
            grid.setColor(0x12FFFFFF);
            grid.setStrokeWidth(Math.max(1f, density * 0.6f));
            setLayerType(View.LAYER_TYPE_HARDWARE, null);
        }

        @Override
        protected void onSizeChanged(int w, int h, int oldw, int oldh) {
            float r = Math.max(w, h);
            base.setShader(new LinearGradient(0, 0, 0, h,
                    new int[]{0xFF04050A, 0xFF0A0E1A, 0xFF05060B}, null, Shader.TileMode.CLAMP));
            glowGold.setShader(new RadialGradient(w * 0.5f, h * 0.34f, r * 0.5f,
                    0x2AFFD400, 0x00FFD400, Shader.TileMode.CLAMP));
            glowBlue.setShader(new RadialGradient(w * 0.88f, h, r * 0.55f,
                    0x2A2F6BFF, 0x002F6BFF, Shader.TileMode.CLAMP));
            vignette.setShader(new RadialGradient(w * 0.5f, h * 0.5f, r * 0.75f,
                    0x00000000, 0xCC000000, Shader.TileMode.CLAMP));

            float step = density * 34f;
            int vc = (int) Math.ceil(w / step);
            int hc = (int) Math.ceil(h / step);
            lines = new float[(vc + hc) * 4];
            int k = 0;
            for (int i = 0; i < vc; i++) {
                float x = i * step;
                lines[k++] = x;
                lines[k++] = 0;
                lines[k++] = x;
                lines[k++] = h;
            }
            for (int j = 0; j < hc; j++) {
                float y = j * step;
                lines[k++] = 0;
                lines[k++] = y;
                lines[k++] = w;
                lines[k++] = y;
            }
        }

        @Override
        protected void onDraw(Canvas canvas) {
            float w = getWidth();
            float h = getHeight();
            canvas.drawRect(0, 0, w, h, base);
            canvas.drawRect(0, 0, w, h, glowGold);
            canvas.drawRect(0, 0, w, h, glowBlue);
            canvas.drawLines(lines, grid);
            canvas.drawRect(0, 0, w, h, vignette);
        }
    }

    /** Cincin progres emas dengan glow, cincin putus-putus berputar, dan titik di ujung busur. */
    private static class RingView extends View {
        private final float d;
        private final Paint track = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint arc = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint dash = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint core = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final RectF oval = new RectF();
        private float progress;
        private float pulse;
        private float rotation;

        RingView(Context ctx, float density) {
            super(ctx);
            this.d = density;
            track.setStyle(Paint.Style.STROKE);
            track.setStrokeWidth(d * 3f);
            track.setColor(0x26FFFFFF);
            arc.setStyle(Paint.Style.STROKE);
            arc.setStrokeCap(Paint.Cap.ROUND);
            dash.setStyle(Paint.Style.STROKE);
            dash.setStrokeWidth(d * 1.2f);
            dash.setColor(0x55FFD400);
            dash.setPathEffect(new DashPathEffect(new float[]{d * 2f, d * 9f}, 0f));
            core.setStyle(Paint.Style.FILL);
            dot.setStyle(Paint.Style.FILL);
        }

        void update(float progress, float pulse, float rotation) {
            this.progress = progress;
            this.pulse = pulse;
            this.rotation = rotation;
            invalidate();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            float w = getWidth();
            float h = getHeight();
            float cx = w / 2f;
            float cy = h / 2f;
            float r = Math.min(w, h) / 2f - d * 12f;

            core.setColor(((int) (14 + 20 * pulse) << 24) | 0x00FFD400);
            canvas.drawCircle(cx, cy, r * 0.92f, core);

            canvas.save();
            canvas.rotate(rotation, cx, cy);
            canvas.drawCircle(cx, cy, r + d * 8f, dash);
            canvas.restore();

            canvas.drawCircle(cx, cy, r, track);

            float sweep = 360f * progress;
            if (sweep > 0.5f) {
                oval.set(cx - r, cy - r, cx + r, cy + r);
                arc.setColor(0x1FFFD400);
                arc.setStrokeWidth(d * 12f);
                canvas.drawArc(oval, -90f, sweep, false, arc);
                arc.setColor(0x45FFD400);
                arc.setStrokeWidth(d * 7f);
                canvas.drawArc(oval, -90f, sweep, false, arc);
                arc.setColor(0xFFFFD400);
                arc.setStrokeWidth(d * 3.4f);
                canvas.drawArc(oval, -90f, sweep, false, arc);

                double a = Math.toRadians(-90.0 + sweep);
                float hx = cx + (float) (r * Math.cos(a));
                float hy = cy + (float) (r * Math.sin(a));
                dot.setColor(0x40FFE766);
                canvas.drawCircle(hx, hy, d * 7f, dot);
                dot.setColor(0xFFFFF1A6);
                canvas.drawCircle(hx, hy, d * 3.2f, dot);
            }
        }
    }
}
