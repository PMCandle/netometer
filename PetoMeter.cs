// Peto Meter - real-time network bandwidth meter for Windows
// Build: run build.bat (uses the C# compiler that ships with Windows)

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Net.NetworkInformation;
using System.Windows.Forms;

class GraphPanel : Panel
{
    public const int Samples = 120;
    public readonly List<double> Down = new List<double>();
    public readonly List<double> Up = new List<double>();
    public static readonly Color DownColor = Color.FromArgb(60, 220, 120);
    public static readonly Color UpColor = Color.FromArgb(255, 160, 50);

    public GraphPanel()
    {
        DoubleBuffered = true;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer, true);
        BackColor = Color.FromArgb(18, 20, 26);
    }

    public void Push(double down, double up)
    {
        Down.Add(down); Up.Add(up);
        while (Down.Count > Samples) Down.RemoveAt(0);
        while (Up.Count > Samples) Up.RemoveAt(0);
        Invalidate();
    }

    public void Clear() { Down.Clear(); Up.Clear(); Invalidate(); }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.Clear(BackColor);

        double max = 10 * 1024;
        foreach (double v in Down) if (v > max) max = v;
        foreach (double v in Up) if (v > max) max = v;
        max *= 1.15;

        using (Pen grid = new Pen(Color.FromArgb(45, 50, 62)))
        {
            for (int i = 1; i < 4; i++)
            {
                float y = Height * i / 4f;
                g.DrawLine(grid, 0, y, Width, y);
            }
        }

        DrawSeries(g, Up, UpColor, max);
        DrawSeries(g, Down, DownColor, max);

        using (Font f = new Font("Segoe UI", 8f))
        using (Brush b = new SolidBrush(Color.FromArgb(140, 150, 170)))
        {
            g.DrawString(Format.Speed(max), f, b, 4, 2);
        }
        using (Pen border = new Pen(Color.FromArgb(60, 66, 80)))
        {
            g.DrawRectangle(border, 0, 0, Width - 1, Height - 1);
        }
    }

    void DrawSeries(Graphics g, List<double> data, Color c, double max)
    {
        if (data.Count < 2) return;
        float step = (float)Width / (Samples - 1);
        float x0 = Width - (data.Count - 1) * step;
        PointF[] pts = new PointF[data.Count];
        for (int i = 0; i < data.Count; i++)
        {
            float x = x0 + i * step;
            float y = (float)(Height - 2 - (data[i] / max) * (Height - 6));
            pts[i] = new PointF(x, y);
        }
        PointF[] poly = new PointF[pts.Length + 2];
        Array.Copy(pts, poly, pts.Length);
        poly[pts.Length] = new PointF(pts[pts.Length - 1].X, Height);
        poly[pts.Length + 1] = new PointF(pts[0].X, Height);
        using (Brush fill = new SolidBrush(Color.FromArgb(55, c)))
            g.FillPolygon(fill, poly);
        using (Pen p = new Pen(c, 1.8f))
            g.DrawLines(p, pts);
    }
}

static class Format
{
    public static string Speed(double bytesPerSec)
    {
        if (bytesPerSec >= 1024.0 * 1024 * 1024) return (bytesPerSec / (1024.0 * 1024 * 1024)).ToString("0.00") + " GB/s";
        if (bytesPerSec >= 1024.0 * 1024) return (bytesPerSec / (1024.0 * 1024)).ToString("0.00") + " MB/s";
        if (bytesPerSec >= 1024.0) return (bytesPerSec / 1024.0).ToString("0.0") + " KB/s";
        return bytesPerSec.ToString("0") + " B/s";
    }

    public static string Size(double bytes)
    {
        if (bytes >= 1024.0 * 1024 * 1024) return (bytes / (1024.0 * 1024 * 1024)).ToString("0.00") + " GB";
        if (bytes >= 1024.0 * 1024) return (bytes / (1024.0 * 1024)).ToString("0.00") + " MB";
        if (bytes >= 1024.0) return (bytes / 1024.0).ToString("0.0") + " KB";
        return bytes.ToString("0") + " B";
    }
}

class PetoMeterForm : Form
{
    GraphPanel graph;
    Label lDown, lUp, lPeak, lTotal;
    Timer timer;
    Stopwatch sw = new Stopwatch();
    long lastRx, lastTx;
    bool first = true;
    string adapterId = null; // null = all adapters
    double totDown, totUp, peakDown, peakUp;
    NotifyIcon tray;
    ContextMenuStrip menu;
    ToolStripMenuItem adaptersItem, topItem, opacityItem;
    Icon appIcon;

    public PetoMeterForm()
    {
        Text = "Peto Meter";
        ClientSize = new Size(360, 196);
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(28, 31, 40);
        ForeColor = Color.White;
        TopMost = true;

        appIcon = MakeIcon();
        Icon = appIcon;

        graph = new GraphPanel();
        graph.SetBounds(10, 10, 340, 110);
        Controls.Add(graph);

        lDown = MakeLabel(10, 128, GraphPanel.DownColor);
        lUp = MakeLabel(185, 128, GraphPanel.UpColor);
        lPeak = MakeLabel(10, 150, Color.FromArgb(170, 180, 200));
        lTotal = MakeLabel(10, 170, Color.FromArgb(170, 180, 200));
        lPeak.Font = new Font("Segoe UI", 8.5f);
        lTotal.Font = new Font("Segoe UI", 8.5f);

        BuildMenu();
        ContextMenuStrip = menu;
        graph.ContextMenuStrip = menu;

        tray = new NotifyIcon();
        tray.Icon = appIcon;
        tray.Text = "Peto Meter";
        tray.ContextMenuStrip = menu;
        tray.Visible = true;
        tray.DoubleClick += delegate { ShowFromTray(); };

        timer = new Timer();
        timer.Interval = 1000;
        timer.Tick += OnTick;
        timer.Start();
        sw.Start();
        UpdateLabels(0, 0);
    }

    Label MakeLabel(int x, int y, Color c)
    {
        Label l = new Label();
        l.AutoSize = true;
        l.Location = new Point(x, y);
        l.ForeColor = c;
        l.BackColor = Color.Transparent;
        l.Font = new Font("Segoe UI Semibold", 10f);
        Controls.Add(l);
        return l;
    }

    Icon MakeIcon()
    {
        using (Bitmap bmp = new Bitmap(32, 32))
        using (Graphics g = Graphics.FromImage(bmp))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(Color.Transparent);
            using (Brush bg = new SolidBrush(Color.FromArgb(28, 31, 40)))
                g.FillEllipse(bg, 1, 1, 30, 30);
            using (Brush d = new SolidBrush(GraphPanel.DownColor))
                g.FillPolygon(d, new PointF[] { new PointF(9, 12), new PointF(15, 12), new PointF(15, 24), new PointF(12, 24) });
            using (Brush u = new SolidBrush(GraphPanel.UpColor))
                g.FillPolygon(u, new PointF[] { new PointF(17, 8), new PointF(23, 8), new PointF(20, 20), new PointF(17, 20) });
            return Icon.FromHandle(bmp.GetHicon());
        }
    }

    void BuildMenu()
    {
        menu = new ContextMenuStrip();
        adaptersItem = new ToolStripMenuItem("Network adapter");
        menu.Opening += delegate { RebuildAdapters(); };

        topItem = new ToolStripMenuItem("Always on top");
        topItem.Checked = true;
        topItem.Click += delegate { TopMost = !TopMost; topItem.Checked = TopMost; };

        opacityItem = new ToolStripMenuItem("Opacity");
        int[] levels = { 100, 85, 70, 50 };
        foreach (int lv in levels)
        {
            int val = lv;
            ToolStripMenuItem it = new ToolStripMenuItem(val + "%");
            it.Click += delegate { Opacity = val / 100.0; };
            opacityItem.DropDownItems.Add(it);
        }

        ToolStripMenuItem reset = new ToolStripMenuItem("Reset totals and peaks");
        reset.Click += delegate { ResetStats(); };

        ToolStripMenuItem showItem = new ToolStripMenuItem("Show window");
        showItem.Click += delegate { ShowFromTray(); };

        ToolStripMenuItem exit = new ToolStripMenuItem("Exit");
        exit.Click += delegate { tray.Visible = false; Application.Exit(); };

        menu.Items.Add(showItem);
        menu.Items.Add(adaptersItem);
        menu.Items.Add(topItem);
        menu.Items.Add(opacityItem);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add(reset);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add(exit);
    }

    void RebuildAdapters()
    {
        adaptersItem.DropDownItems.Clear();
        ToolStripMenuItem all = new ToolStripMenuItem("All adapters");
        all.Checked = adapterId == null;
        all.Click += delegate { SelectAdapter(null); };
        adaptersItem.DropDownItems.Add(all);
        foreach (NetworkInterface nic in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (nic.NetworkInterfaceType == NetworkInterfaceType.Loopback ||
                nic.NetworkInterfaceType == NetworkInterfaceType.Tunnel) continue;
            string id = nic.Id;
            ToolStripMenuItem it = new ToolStripMenuItem(nic.Name);
            it.Checked = adapterId == id;
            it.Click += delegate { SelectAdapter(id); };
            adaptersItem.DropDownItems.Add(it);
        }
    }

    void SelectAdapter(string id)
    {
        adapterId = id;
        first = true;
    }

    void ResetStats()
    {
        totDown = totUp = peakDown = peakUp = 0;
        graph.Clear();
        UpdateLabels(0, 0);
    }

    void ShowFromTray()
    {
        Show();
        WindowState = FormWindowState.Normal;
        Activate();
    }

    protected override void OnResize(EventArgs e)
    {
        base.OnResize(e);
        if (WindowState == FormWindowState.Minimized) Hide();
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        tray.Visible = false;
        base.OnFormClosing(e);
    }

    void ReadCounters(out long rx, out long tx)
    {
        rx = 0; tx = 0;
        foreach (NetworkInterface nic in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (nic.OperationalStatus != OperationalStatus.Up) continue;
            if (nic.NetworkInterfaceType == NetworkInterfaceType.Loopback ||
                nic.NetworkInterfaceType == NetworkInterfaceType.Tunnel) continue;
            if (adapterId != null && nic.Id != adapterId) continue;
            try
            {
                IPv4InterfaceStatistics s = nic.GetIPv4Statistics();
                rx += s.BytesReceived;
                tx += s.BytesSent;
            }
            catch { }
        }
    }

    void OnTick(object sender, EventArgs e)
    {
        long rx, tx;
        ReadCounters(out rx, out tx);
        if (first)
        {
            lastRx = rx; lastTx = tx; first = false;
            sw.Reset(); sw.Start();
            return;
        }
        double dt = sw.Elapsed.TotalSeconds;
        sw.Reset(); sw.Start();
        if (dt <= 0.05) dt = 1.0;

        long dRx = rx - lastRx; if (dRx < 0) dRx = 0;
        long dTx = tx - lastTx; if (dTx < 0) dTx = 0;
        lastRx = rx; lastTx = tx;

        double down = dRx / dt;
        double up = dTx / dt;
        totDown += dRx; totUp += dTx;
        if (down > peakDown) peakDown = down;
        if (up > peakUp) peakUp = up;

        graph.Push(down, up);
        UpdateLabels(down, up);
    }

    void UpdateLabels(double down, double up)
    {
        lDown.Text = "▼ " + Format.Speed(down);
        lUp.Text = "▲ " + Format.Speed(up);
        lPeak.Text = "Peak:  ▼ " + Format.Speed(peakDown) + "    ▲ " + Format.Speed(peakUp);
        lTotal.Text = "Total: ▼ " + Format.Size(totDown) + "    ▲ " + Format.Size(totUp);
        tray.Text = "Peto Meter  D " + Format.Speed(down) + "  U " + Format.Speed(up);
    }
}

static class Program
{
    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new PetoMeterForm());
    }
}