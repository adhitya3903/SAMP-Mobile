package com.samp.mobile.launcher;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import com.samp.mobile.R;
import com.samp.mobile.game.SAMP;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Launcher Acropolize di dalam aplikasi: pilih/tambah server, nama, versi SA-MP,
 * lalu menulis settings.ini otomatis dan menjalankan game.
 * Tidak memakai server luar (tidak butuh internet untuk membuka launcher ini).
 */
public class AcropolizeLauncherActivity extends Activity {

    // ===================== EDIT DI SINI =====================
    private static final String APP_TITLE = "ACROPOLIZE ROLEPLAY";
    private static final String TAGLINE = "Together We Are One";
    // Server bawaan {nama, alamat}. Contoh: { {"Acropolize", "123.45.67.89:7777"} }
    // Biarkan kosong kalau tidak mau ada server bawaan.
    private static final String[][] DEFAULT_SERVERS = { };
    private static final String[] VERSIONS = { "0.3.7", "0.3.7-R5", "0.3.DL-R1" };
    private static final String DEFAULT_VERSION = "0.3.7-R5";
    // ========================================================

    private static final int ACCENT = Color.parseColor("#FFD400");
    private static final int BG = Color.parseColor("#0F0F12");
    private static final int PANEL = Color.parseColor("#18181D");
    private static final int FIELD = Color.parseColor("#21212A");
    private static final int STROKE = Color.parseColor("#2E2E38");
    private static final int TEXT = Color.parseColor("#EBEBEE");
    private static final int MUTED = Color.parseColor("#91919B");
    private static final int DANGER = Color.parseColor("#FF6347");
    private static final int OK = Color.parseColor("#33CC55");

    private static final Pattern NICK =
            Pattern.compile("^[A-Za-z0-9_\\[\\]\\.\\$=@\\(\\)]{3,24}$");

    private static final String DEFAULT_INI =
            "[client]\n"
            + "name = \n"
            + "password = \n"
            + "host = 127.0.0.1\n"
            + "port = 7777\n"
            + "version = 0.3.7\n"
            + "\n"
            + "[debug]\n"
            + "debug = false\n"
            + "online = true\n"
            + "\n"
            + "[gui]\n"
            + "androidkeyboard = true\n"
            + "autoaim = true\n"
            + "fps = 1\n"
            + "FPSLimit = 90\n"
            + "ChatMaxMessages = 8\n"
            + "Font = arial.ttf\n"
            + "FontSize = 30.000000\n"
            + "FontOutline = 2\n"
            + "ChatPosX = 325.000000\n"
            + "ChatPosY = 25.000000\n"
            + "ChatSizeX = 1150.000000\n"
            + "ChatSizeY = 220.000000\n"
            + "HealthBarWidth = 60.000000\n"
            + "HealthBarHeight = 10.000000\n"
            + "MicrophoneSize = 150.000000\n"
            + "MicrophoneX = 1450.000000\n"
            + "MicrophoneY = 600.000000\n";

    private static class Server {
        String name = "";
        String host = "";
        int port = 7777;
        String password = "";
    }

    private SharedPreferences prefs;
    private final List<Server> servers = new ArrayList<Server>();
    private int selected = -1;
    private String version = DEFAULT_VERSION;

    private EditText etNick;
    private LinearLayout serverListBox;
    private LinearLayout versionRow;
    private TextView tvStatus;

    // ------------------------------------------------------------------ lifecycle

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("acropolize_launcher", MODE_PRIVATE);
        loadState();
        buildUi();
        refreshServers();
        refreshVersions();
        refreshStatus();
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshStatus();
    }

    @Override
    protected void onPause() {
        super.onPause();
        saveState();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            getWindow().getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        }
    }

    // ------------------------------------------------------------------ helpers (UI)

    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density + 0.5f);
    }

    private GradientDrawable box(int fill, int stroke, int radiusDp) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill);
        g.setCornerRadius(dp(radiusDp));
        if (stroke != 0) g.setStroke(dp(1), stroke);
        return g;
    }

    private TextView text(String s, int sp, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private TextView sectionLabel(String s) {
        TextView t = text(s, 11, ACCENT, true);
        t.setLetterSpacing(0.18f);
        t.setPadding(dp(2), dp(14), 0, dp(6));
        return t;
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_LONG).show();
    }

    // ------------------------------------------------------------------ UI

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.HORIZONTAL);
        root.setBackgroundColor(BG);
        root.setPadding(dp(24), dp(12), dp(24), dp(12));

        // ---- kiri: logo
        LinearLayout left = new LinearLayout(this);
        left.setOrientation(LinearLayout.VERTICAL);
        left.setGravity(Gravity.CENTER);

        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.acro_logo);
        logo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        left.addView(logo, new LinearLayout.LayoutParams(dp(150), dp(180)));

        TextView title = text(APP_TITLE, 15, ACCENT, true);
        title.setGravity(Gravity.CENTER);
        title.setLetterSpacing(0.08f);
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        tlp.topMargin = dp(8);
        left.addView(title, tlp);

        TextView tag = text("\u201C" + TAGLINE + "\u201D", 12, MUTED, false);
        tag.setTypeface(Typeface.DEFAULT, Typeface.ITALIC);
        tag.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams glp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        glp.topMargin = dp(4);
        left.addView(tag, glp);

        root.addView(left, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f));

        // ---- kanan: pengaturan + tombol MAIN
        LinearLayout right = new LinearLayout(this);
        right.setOrientation(LinearLayout.VERTICAL);
        right.setPadding(dp(16), 0, 0, 0);

        ScrollView sv = new ScrollView(this);
        sv.setFillViewport(false);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        sv.addView(content, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        // pemain
        content.addView(sectionLabel("PEMAIN"));
        etNick = new EditText(this);
        etNick.setHint("Nama karakter (contoh: Nama_Karakter)");
        etNick.setHintTextColor(MUTED);
        etNick.setTextColor(TEXT);
        etNick.setTextSize(15);
        etNick.setSingleLine(true);
        etNick.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        etNick.setBackground(box(FIELD, STROKE, 10));
        etNick.setPadding(dp(14), dp(10), dp(14), dp(10));
        etNick.setText(prefs.getString("nick", ""));
        content.addView(etNick, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        // server
        content.addView(sectionLabel("SERVER"));
        serverListBox = new LinearLayout(this);
        serverListBox.setOrientation(LinearLayout.VERTICAL);
        content.addView(serverListBox, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView add = text("+  Tambah server", 14, ACCENT, true);
        add.setGravity(Gravity.CENTER);
        add.setBackground(box(PANEL, ACCENT, 10));
        add.setPadding(dp(14), dp(10), dp(14), dp(10));
        add.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                showAddServerDialog();
            }
        });
        content.addView(add, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        // versi
        content.addView(sectionLabel("VERSI SA-MP"));
        versionRow = new LinearLayout(this);
        versionRow.setOrientation(LinearLayout.HORIZONTAL);
        content.addView(versionRow, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        TextView vhint = text("Kalau server menolak koneksi, coba versi lain.", 11, MUTED, false);
        vhint.setPadding(dp(2), dp(6), 0, 0);
        content.addView(vhint);

        // status data game
        tvStatus = text("", 12, MUTED, false);
        tvStatus.setPadding(dp(2), dp(14), 0, dp(8));
        content.addView(tvStatus);

        right.addView(sv, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        TextView main = text("MAIN", 18, Color.BLACK, true);
        main.setGravity(Gravity.CENTER);
        main.setLetterSpacing(0.15f);
        main.setBackground(box(ACCENT, 0, 12));
        main.setPadding(dp(14), dp(12), dp(14), dp(12));
        main.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                onMainClicked();
            }
        });
        LinearLayout.LayoutParams mlp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        mlp.topMargin = dp(8);
        right.addView(main, mlp);

        root.addView(right, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1.7f));
        setContentView(root);
    }

    private void refreshServers() {
        serverListBox.removeAllViews();
        if (servers.isEmpty()) {
            TextView empty = text("Belum ada server. Tambahkan alamat server kamu.", 13, MUTED, false);
            empty.setPadding(dp(2), dp(2), 0, dp(10));
            serverListBox.addView(empty);
            return;
        }
        for (int i = 0; i < servers.size(); i++) {
            final int idx = i;
            Server s = servers.get(i);
            boolean sel = (i == selected);

            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(14), dp(10), dp(10), dp(10));
            row.setBackground(box(sel ? Color.parseColor("#2B2810") : FIELD, sel ? ACCENT : STROKE, 10));

            LinearLayout info = new LinearLayout(this);
            info.setOrientation(LinearLayout.VERTICAL);
            info.addView(text(s.name, 15, TEXT, true));
            info.addView(text(s.host + ":" + s.port, 12, MUTED, false));
            row.addView(info, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

            TextView del = text("Hapus", 12, DANGER, true);
            del.setPadding(dp(10), dp(6), dp(6), dp(6));
            del.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    confirmDelete(idx);
                }
            });
            row.addView(del);

            row.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    selected = idx;
                    saveState();
                    refreshServers();
                }
            });

            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.bottomMargin = dp(8);
            serverListBox.addView(row, lp);
        }
    }

    private void refreshVersions() {
        versionRow.removeAllViews();
        for (int i = 0; i < VERSIONS.length; i++) {
            final String v = VERSIONS[i];
            boolean sel = v.equals(version);
            TextView chip = text(v, 13, sel ? Color.BLACK : TEXT, true);
            chip.setGravity(Gravity.CENTER);
            chip.setBackground(box(sel ? ACCENT : FIELD, sel ? 0 : STROKE, 20));
            chip.setPadding(dp(14), dp(8), dp(14), dp(8));
            chip.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View view) {
                    version = v;
                    saveState();
                    refreshVersions();
                }
            });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.rightMargin = dp(8);
            versionRow.addView(chip, lp);
        }
    }

    private void refreshStatus() {
        if (tvStatus == null) return;
        File root = getExternalFilesDir(null);
        if (dataReady()) {
            tvStatus.setTextColor(OK);
            tvStatus.setText("Data game ditemukan.");
        } else {
            tvStatus.setTextColor(DANGER);
            tvStatus.setText("Data game belum ditemukan di:\n"
                    + (root != null ? root.getAbsolutePath() : "(penyimpanan tidak tersedia)")
                    + "\nSalin isi folder Files (data, models, Textures, SAMP, dst) ke folder itu.");
        }
    }

    // ------------------------------------------------------------------ dialogs

    private EditText dialogField(String hint) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setSingleLine(true);
        e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        return e;
    }

    private void showAddServerDialog() {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(20), dp(8), dp(20), dp(0));

        final EditText etName = dialogField("Nama server (opsional)");
        final EditText etAddr = dialogField("Alamat, contoh: 123.45.67.89:7777");
        final EditText etPass = dialogField("Kata sandi (hanya jika server memerlukannya)");
        etPass.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        form.addView(etName);
        form.addView(etAddr);
        form.addView(etPass);

        final AlertDialog dlg = new AlertDialog.Builder(this)
                .setTitle("Tambah server")
                .setView(form)
                .setPositiveButton("Tambah", null)
                .setNegativeButton("Batal", null)
                .create();
        dlg.show();
        dlg.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Server s = parseServer(etName.getText().toString(),
                        etAddr.getText().toString(),
                        etPass.getText().toString());
                if (s == null) {
                    toast("Alamat tidak valid. Contoh: 123.45.67.89:7777 (port 1-65535)");
                    return;
                }
                servers.add(s);
                selected = servers.size() - 1;
                saveState();
                refreshServers();
                dlg.dismiss();
            }
        });
    }

    private void confirmDelete(final int idx) {
        if (idx < 0 || idx >= servers.size()) return;
        new AlertDialog.Builder(this)
                .setTitle("Hapus server")
                .setMessage("Hapus \"" + servers.get(idx).name + "\" dari daftar?")
                .setPositiveButton("Hapus", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int which) {
                        servers.remove(idx);
                        if (selected >= servers.size()) selected = servers.size() - 1;
                        saveState();
                        refreshServers();
                    }
                })
                .setNegativeButton("Batal", null)
                .show();
    }

    // ------------------------------------------------------------------ logic

    private Server parseServer(String name, String addr, String pass) {
        addr = addr.trim();
        String host = addr;
        int port = 7777;
        int c = addr.lastIndexOf(':');
        if (c > 0) {
            host = addr.substring(0, c).trim();
            try {
                port = Integer.parseInt(addr.substring(c + 1).trim());
            } catch (NumberFormatException e) {
                return null;
            }
        }
        if (host.length() == 0 || !host.matches("[A-Za-z0-9.\\-]+") || port < 1 || port > 65535) {
            return null;
        }
        Server s = new Server();
        s.host = host;
        s.port = port;
        s.name = name.trim().length() > 0 ? name.trim() : host + ":" + port;
        s.password = pass.replace("\n", "").replace("\r", "");
        return s;
    }

    private void loadState() {
        servers.clear();
        String raw = prefs.getString("servers", null);
        if (raw == null) {
            for (int i = 0; i < DEFAULT_SERVERS.length; i++) {
                Server s = parseServer(DEFAULT_SERVERS[i][0], DEFAULT_SERVERS[i][1], "");
                if (s != null) servers.add(s);
            }
        } else {
            try {
                JSONArray a = new JSONArray(raw);
                for (int i = 0; i < a.length(); i++) {
                    JSONObject o = a.getJSONObject(i);
                    Server s = new Server();
                    s.name = o.optString("name", "");
                    s.host = o.optString("host", "");
                    s.port = o.optInt("port", 7777);
                    s.password = o.optString("password", "");
                    if (s.host.length() > 0) servers.add(s);
                }
            } catch (Exception ignored) {
            }
        }
        selected = prefs.getInt("selected", servers.isEmpty() ? -1 : 0);
        if (selected >= servers.size()) selected = servers.isEmpty() ? -1 : 0;

        version = prefs.getString("version", DEFAULT_VERSION);
        boolean known = false;
        for (int i = 0; i < VERSIONS.length; i++) if (VERSIONS[i].equals(version)) known = true;
        if (!known) version = DEFAULT_VERSION;
    }

    private void saveState() {
        JSONArray a = new JSONArray();
        for (int i = 0; i < servers.size(); i++) {
            Server s = servers.get(i);
            try {
                JSONObject o = new JSONObject();
                o.put("name", s.name);
                o.put("host", s.host);
                o.put("port", s.port);
                o.put("password", s.password);
                a.put(o);
            } catch (Exception ignored) {
            }
        }
        String nick = etNick != null ? etNick.getText().toString().trim() : prefs.getString("nick", "");
        prefs.edit()
                .putString("servers", a.toString())
                .putInt("selected", selected)
                .putString("version", version)
                .putString("nick", nick)
                .apply();
    }

    private boolean dataReady() {
        File root = getExternalFilesDir(null);
        return root != null
                && new File(root, "data").isDirectory()
                && new File(root, "models").isDirectory();
    }

    private void onMainClicked() {
        final String nick = etNick.getText().toString().trim();
        if (!NICK.matcher(nick).matches()) {
            toast("Nama tidak valid (3-24 karakter: huruf, angka, _ [ ] . $ = @ ( ) ).");
            return;
        }
        if (selected < 0 || selected >= servers.size()) {
            toast("Pilih atau tambah server dulu.");
            return;
        }
        final Server s = servers.get(selected);
        saveState();

        if (!dataReady()) {
            new AlertDialog.Builder(this)
                    .setTitle("Data game belum lengkap")
                    .setMessage("Folder data game tidak ditemukan. Game kemungkinan akan langsung tertutup.\n\n"
                            + "Lanjutkan juga?")
                    .setPositiveButton("Tetap main", new DialogInterface.OnClickListener() {
                        @Override
                        public void onClick(DialogInterface d, int which) {
                            launch(nick, s);
                        }
                    })
                    .setNegativeButton("Batal", null)
                    .show();
            return;
        }
        launch(nick, s);
    }

    private void launch(String nick, Server s) {
        try {
            writeSettings(nick, s);
            startActivity(new Intent(this, SAMP.class));
            finish();
        } catch (Exception e) {
            toast("Gagal menyiapkan pengaturan: " + e.getMessage());
        }
    }

    // ------------------------------------------------------------------ settings.ini

    private void writeSettings(String nick, Server s) throws Exception {
        File root = getExternalFilesDir(null);
        if (root == null) throw new Exception("penyimpanan tidak tersedia");
        File dir = new File(root, "SAMP");
        if (!dir.exists() && !dir.mkdirs()) throw new Exception("tidak bisa membuat folder " + dir);
        File ini = new File(dir, "settings.ini");

        List<String> lines = new ArrayList<String>();
        if (ini.exists()) {
            BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(ini), "UTF-8"));
            try {
                String ln;
                while ((ln = br.readLine()) != null) lines.add(ln);
            } finally {
                br.close();
            }
        } else {
            String[] def = DEFAULT_INI.split("\n");
            for (int i = 0; i < def.length; i++) lines.add(def[i]);
        }

        String[][] kv = {
                { "name", nick },
                { "password", s.password },
                { "host", s.host },
                { "port", String.valueOf(s.port) },
                { "version", version }
        };
        List<String> out = applyClient(lines, kv);

        OutputStreamWriter w = new OutputStreamWriter(new FileOutputStream(ini, false), "UTF-8");
        try {
            for (int i = 0; i < out.size(); i++) {
                w.write(out.get(i));
                w.write("\n");
            }
        } finally {
            w.close();
        }
    }

    private int keyIndex(String[][] kv, String key) {
        for (int i = 0; i < kv.length; i++) if (kv[i][0].equalsIgnoreCase(key)) return i;
        return -1;
    }

    private void addMissing(List<String> out, boolean[] done, String[][] kv) {
        for (int i = 0; i < kv.length; i++) {
            if (!done[i]) {
                out.add(kv[i][0] + " = " + kv[i][1]);
                done[i] = true;
            }
        }
    }

    /** Mengganti kunci di bagian [client] saja; bagian lain dibiarkan apa adanya. */
    private List<String> applyClient(List<String> lines, String[][] kv) {
        List<String> out = new ArrayList<String>();
        boolean[] done = new boolean[kv.length];
        String section = "";
        boolean sawClient = false;

        for (int n = 0; n < lines.size(); n++) {
            String line = lines.get(n);
            String t = line.trim();

            if (t.startsWith("[") && t.endsWith("]")) {
                if (section.equals("client")) addMissing(out, done, kv);
                section = t.substring(1, t.length() - 1).trim().toLowerCase();
                if (section.equals("client")) sawClient = true;
                out.add(line);
                continue;
            }

            if (section.equals("client") && t.length() > 0 && !t.startsWith(";") && !t.startsWith("#")) {
                int eq = t.indexOf('=');
                if (eq > 0) {
                    int k = keyIndex(kv, t.substring(0, eq).trim());
                    if (k >= 0) {
                        out.add(kv[k][0] + " = " + kv[k][1]);
                        done[k] = true;
                        continue;
                    }
                }
            }
            out.add(line);
        }

        if (section.equals("client")) addMissing(out, done, kv);

        if (!sawClient) {
            List<String> head = new ArrayList<String>();
            head.add("[client]");
            addMissing(head, done, kv);
            head.add("");
            head.addAll(out);
            out = head;
        }
        return out;
    }
}
