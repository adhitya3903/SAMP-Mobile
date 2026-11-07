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
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Launcher Acropolize di dalam aplikasi. Tampilannya mengikuti launcher PC:
 * header, panel kiri bergradasi emas, "Selamat Datang", tombol MAIN kuning.
 * Menulis settings.ini otomatis lalu menjalankan game. Tidak butuh server luar.
 */
public class AcropolizeLauncherActivity extends Activity {

    // ===================== EDIT DI SINI =====================
    private static final String HEADER_TITLE = "ACROPOLIZE ROLEPLAY  \u2022  LAUNCHER";
    private static final String TAGLINE = "Together We Are One";
    private static final String FOOTER = "\u00A9 2026 Hachiroku  \u2022  Acropolize Roleplay   v2.1.0";
    // Server bawaan {nama, alamat}. Contoh: { {"Acropolize", "123.45.67.89:7777"} }
    private static final String[][] DEFAULT_SERVERS = { };
    private static final String[] VERSIONS = { "0.3.7", "0.3.7-R5", "0.3.DL-R1" };
    private static final String DEFAULT_VERSION = "0.3.7-R5";
    // ========================================================

    // Warna sama dengan launcher PC
    private static final int BG = Color.rgb(15, 15, 18);
    private static final int PANEL = Color.rgb(24, 24, 29);
    private static final int FIELD = Color.rgb(33, 33, 39);
    private static final int ACCENT = Color.rgb(255, 212, 0);
    private static final int TEXT = Color.rgb(235, 235, 238);
    private static final int MUTED = Color.rgb(145, 145, 155);
    private static final int DANGER = Color.rgb(255, 99, 71);
    private static final int OK = Color.rgb(51, 204, 85);
    private static final int STROKE = Color.rgb(60, 60, 68);
    private static final int GOLD_TOP = Color.rgb(44, 37, 0);

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
        // status (tidak disimpan)
        boolean checking = false;
        boolean checked = false;
        boolean online = false;
        int players = -1;
        int maxPlayers = -1;
        long ping = -1;
    }

    private SharedPreferences prefs;
    private final List<Server> servers = new ArrayList<Server>();
    private int selected = -1;
    private String version = DEFAULT_VERSION;

    private EditText etNick;
    private LinearLayout serverListBox;
    private LinearLayout versionRow;
    private TextView tvStatus;
    private TextView tvServerState;
    private TextView tvPlayers;

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
        refreshLeftStatus();
        queryAll();
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

    private TextView fieldLabel(String s) {
        TextView t = text(s, 12, TEXT, true);
        t.setPadding(dp(2), dp(12), 0, dp(5));
        return t;
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_LONG).show();
    }

    private LinearLayout.LayoutParams lp(int w, int h) {
        return new LinearLayout.LayoutParams(w, h);
    }

    // ------------------------------------------------------------------ UI

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);

        // ---- header (seperti launcher PC)
        TextView header = text(HEADER_TITLE, 10, MUTED, true);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setBackgroundColor(PANEL);
        header.setPadding(dp(16), 0, dp(16), 0);
        root.addView(header, lp(ViewGroup.LayoutParams.MATCH_PARENT, dp(34)));

        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.HORIZONTAL);
        root.addView(body, lp(ViewGroup.LayoutParams.MATCH_PARENT, 0));
        ((LinearLayout.LayoutParams) body.getLayoutParams()).weight = 1f;

        // ---- panel kiri: logo, status server, tagline (gradasi emas -> gelap)
        LinearLayout left = new LinearLayout(this);
        left.setOrientation(LinearLayout.VERTICAL);
        left.setGravity(Gravity.CENTER_HORIZONTAL);
        GradientDrawable grad = new GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM, new int[] { GOLD_TOP, BG });
        left.setBackground(grad);
        left.setPadding(dp(12), dp(14), dp(12), dp(14));

        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.acro_logo);
        logo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        left.addView(logo, lp(dp(150), dp(170)));

        tvServerState = text("\u25CF Memeriksa server...", 13, MUTED, true);
        tvServerState.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams sl = lp(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        sl.topMargin = dp(10);
        left.addView(tvServerState, sl);

        tvPlayers = text("", 11, MUTED, false);
        tvPlayers.setGravity(Gravity.CENTER);
        left.addView(tvPlayers, lp(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        View spacer = new View(this);
        left.addView(spacer, lp(1, 0));
        ((LinearLayout.LayoutParams) spacer.getLayoutParams()).weight = 1f;

        TextView tag = text("\u201C" + TAGLINE + "\u201D", 12, ACCENT, false);
        tag.setTypeface(Typeface.DEFAULT, Typeface.ITALIC);
        tag.setGravity(Gravity.CENTER);
        left.addView(tag, lp(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        body.addView(left, lp(0, ViewGroup.LayoutParams.MATCH_PARENT));
        ((LinearLayout.LayoutParams) left.getLayoutParams()).weight = 1f;

        // ---- panel kanan
        LinearLayout right = new LinearLayout(this);
        right.setOrientation(LinearLayout.VERTICAL);
        right.setPadding(dp(24), dp(8), dp(24), dp(6));

        ScrollView sv = new ScrollView(this);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        sv.addView(content, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView welcome = text("Selamat Datang", 22, ACCENT, true);
        content.addView(welcome);
        TextView sub = text("Masuk lewat launcher resmi untuk bermain dengan aman dan adil.", 12, MUTED, false);
        content.addView(sub);

        content.addView(fieldLabel("Nama karakter"));
        etNick = new EditText(this);
        etNick.setHint("Contoh: Nama_Karakter");
        etNick.setHintTextColor(MUTED);
        etNick.setTextColor(TEXT);
        etNick.setTextSize(15);
        etNick.setSingleLine(true);
        etNick.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        etNick.setBackground(box(FIELD, STROKE, 6));
        etNick.setPadding(dp(12), dp(9), dp(12), dp(9));
        etNick.setText(prefs.getString("nick", ""));
        content.addView(etNick, lp(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        content.addView(fieldLabel("Server"));
        serverListBox = new LinearLayout(this);
        serverListBox.setOrientation(LinearLayout.VERTICAL);
        content.addView(serverListBox, lp(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView add = text("+  Tambah server", 13, TEXT, true);
        add.setGravity(Gravity.CENTER);
        add.setBackground(box(PANEL, STROKE, 6));
        add.setPadding(dp(14), dp(9), dp(14), dp(9));
        add.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                showAddServerDialog();
            }
        });
        content.addView(add, lp(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        content.addView(fieldLabel("Versi SA-MP"));
        versionRow = new LinearLayout(this);
        versionRow.setOrientation(LinearLayout.HORIZONTAL);
        content.addView(versionRow, lp(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        TextView vhint = text("Kalau server menolak koneksi, coba versi lain.", 11, MUTED, false);
        vhint.setPadding(dp(2), dp(5), 0, 0);
        content.addView(vhint);

        tvStatus = text("", 11, MUTED, false);
        tvStatus.setPadding(dp(2), dp(12), 0, dp(6));
        content.addView(tvStatus);

        right.addView(sv, lp(ViewGroup.LayoutParams.MATCH_PARENT, 0));
        ((LinearLayout.LayoutParams) sv.getLayoutParams()).weight = 1f;

        TextView main = text("MAIN", 17, Color.BLACK, true);
        main.setGravity(Gravity.CENTER);
        main.setBackground(box(ACCENT, 0, 4));
        main.setPadding(dp(14), dp(11), dp(14), dp(11));
        main.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                onMainClicked();
            }
        });
        LinearLayout.LayoutParams mlp = lp(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        mlp.topMargin = dp(6);
        right.addView(main, mlp);

        TextView footer = text(FOOTER, 9, MUTED, false);
        footer.setGravity(Gravity.END);
        footer.setPadding(0, dp(6), 0, 0);
        right.addView(footer, lp(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        body.addView(right, lp(0, ViewGroup.LayoutParams.MATCH_PARENT));
        ((LinearLayout.LayoutParams) right.getLayoutParams()).weight = 1.7f;

        setContentView(root);
    }

    private String serverLine(Server s) {
        if (s.checking && !s.checked) return "Memeriksa...";
        if (!s.checked) return "";
        if (s.online) {
            return s.players + " / " + s.maxPlayers + " pemain  \u2022  " + s.ping + " ms";
        }
        return "Tidak merespons (query)";
    }

    private void refreshServers() {
        serverListBox.removeAllViews();
        if (servers.isEmpty()) {
            TextView empty = text("Belum ada server. Tambahkan alamat server kamu.", 12, MUTED, false);
            empty.setPadding(dp(2), dp(2), 0, dp(8));
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
            row.setPadding(dp(12), dp(8), dp(8), dp(8));
            row.setBackground(box(sel ? Color.rgb(43, 40, 16) : FIELD, sel ? ACCENT : STROKE, 6));

            LinearLayout info = new LinearLayout(this);
            info.setOrientation(LinearLayout.VERTICAL);
            String addr = s.host + ":" + s.port;
            info.addView(text(s.name.equals(addr) ? addr : s.name, 14, TEXT, true));
            if (!s.name.equals(addr)) info.addView(text(addr, 11, MUTED, false));
            String st = serverLine(s);
            if (st.length() > 0) {
                int c = !s.checked ? MUTED : (s.online ? OK : DANGER);
                info.addView(text(st, 11, c, false));
            }
            row.addView(info, lp(0, ViewGroup.LayoutParams.WRAP_CONTENT));
            ((LinearLayout.LayoutParams) info.getLayoutParams()).weight = 1f;

            TextView del = text("Hapus", 11, DANGER, true);
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
                    refreshLeftStatus();
                }
            });

            LinearLayout.LayoutParams l = lp(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            l.bottomMargin = dp(6);
            serverListBox.addView(row, l);
        }
    }

    private void refreshLeftStatus() {
        if (tvServerState == null) return;
        if (selected < 0 || selected >= servers.size()) {
            tvServerState.setTextColor(MUTED);
            tvServerState.setText("\u25CF Belum ada server");
            tvPlayers.setText("");
            return;
        }
        Server s = servers.get(selected);
        if (!s.checked) {
            tvServerState.setTextColor(MUTED);
            tvServerState.setText("\u25CF Memeriksa server...");
            tvPlayers.setText("");
        } else if (s.online) {
            tvServerState.setTextColor(OK);
            tvServerState.setText("\u25CF Server Online");
            tvPlayers.setText(s.players + " / " + s.maxPlayers + " pemain");
        } else {
            tvServerState.setTextColor(DANGER);
            tvServerState.setText("\u25CF Server Offline");
            tvPlayers.setText("");
        }
    }

    private void refreshVersions() {
        versionRow.removeAllViews();
        for (int i = 0; i < VERSIONS.length; i++) {
            final String v = VERSIONS[i];
            boolean sel = v.equals(version);
            TextView chip = text(v, 12, sel ? Color.BLACK : TEXT, true);
            chip.setGravity(Gravity.CENTER);
            chip.setBackground(box(sel ? ACCENT : FIELD, sel ? 0 : STROKE, 16));
            chip.setPadding(dp(12), dp(7), dp(12), dp(7));
            chip.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View view) {
                    version = v;
                    saveState();
                    refreshVersions();
                }
            });
            LinearLayout.LayoutParams l = lp(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            l.rightMargin = dp(8);
            versionRow.addView(chip, l);
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

    // ------------------------------------------------------------------ cek status server (query UDP SA-MP)

    private void queryAll() {
        for (int i = 0; i < servers.size(); i++) queryServer(servers.get(i));
    }

    private void queryServer(final Server s) {
        s.checking = true;
        s.checked = false;
        new Thread(new Runnable() {
            @Override
            public void run() {
                boolean ok = false;
                int pl = -1;
                int mx = -1;
                long ping = -1;
                DatagramSocket sock = null;
                try {
                    InetAddress addr = InetAddress.getByName(s.host);
                    byte[] ip = addr.getAddress();
                    if (ip.length == 4) {
                        byte[] req = new byte[11];
                        req[0] = 'S';
                        req[1] = 'A';
                        req[2] = 'M';
                        req[3] = 'P';
                        req[4] = ip[0];
                        req[5] = ip[1];
                        req[6] = ip[2];
                        req[7] = ip[3];
                        req[8] = (byte) (s.port & 0xFF);
                        req[9] = (byte) ((s.port >> 8) & 0xFF);
                        req[10] = 'i';
                        sock = new DatagramSocket();
                        sock.setSoTimeout(2500);
                        long t0 = System.currentTimeMillis();
                        sock.send(new DatagramPacket(req, req.length, addr, s.port));
                        byte[] buf = new byte[512];
                        DatagramPacket resp = new DatagramPacket(buf, buf.length);
                        sock.receive(resp);
                        ping = System.currentTimeMillis() - t0;
                        if (resp.getLength() >= 16 && buf[0] == 'S' && buf[1] == 'A'
                                && buf[2] == 'M' && buf[3] == 'P' && buf[10] == 'i') {
                            ok = true;
                            pl = (buf[12] & 0xFF) | ((buf[13] & 0xFF) << 8);
                            mx = (buf[14] & 0xFF) | ((buf[15] & 0xFF) << 8);
                        }
                    }
                } catch (Exception e) {
                    ok = false;
                } finally {
                    if (sock != null) sock.close();
                }
                s.online = ok;
                s.players = pl;
                s.maxPlayers = mx;
                s.ping = ping;
                s.checking = false;
                s.checked = true;
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        if (isFinishing()) return;
                        refreshServers();
                        refreshLeftStatus();
                    }
                });
            }
        }).start();
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
                refreshLeftStatus();
                queryServer(s);
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
                        refreshLeftStatus();
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
                    if (s.name.length() == 0) s.name = s.host + ":" + s.port;
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
