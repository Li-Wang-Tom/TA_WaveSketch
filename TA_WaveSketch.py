# -*- coding: utf-8 -*-
"""
TA_TimingAnalyzer (TA_TimingAnalyzer.py)
-----------------------------------------
クリック操作でタイミングチャート
(ON/OFF、Data/Clear、注釈、トリガ/条件矢印、タイマーバー)
を組み立ててられるGUIツール Techno仕様

使い方:
  ・グリッド 左クリック            : そのセルのON/OFF、またはData/Clearを切り替える
  ・グリッド 右クリック            : そのセルの自由テキスト/注釈を編集する
  ・「Arrow Mode」ボタン(トグル)    : ONにすると、全ての行に「スナップできる点」が
    小さいドットで表示される(実際のON/OFF切り替わりの角＋各マスの中間点)。
    1回目のクリックで矢印の始点(赤く強調表示される)、2回目のクリックで終点を
    決めるとTrigger/Conditionを選ぶダイアログが出る。
    ドラッグではなく「クリック→クリック」の2ステップ方式にしているのは、
    ドラッグだと離す場所を誤りやすい(ミスが多い)。
      ・右クリックで、選択中の始点をキャンセルできる。
  ・ヘッダ帯(「Timing chart」の文字がある行)クリック : 一番近い縦線を
    太字にする/戻す
  ・左側の信号名クリック            : 信号名を変更する
  ・左側のバッジクリック            : 所属テキストとバッジの色を変更する
  ・左側の信号名を右クリック        : 複製・削除メニューを出す

このファイル内の命名ルール:
  - 自作の状態変数には先頭に "var" を付ける
  - 自作のメソッド(処理を行う関数)には先頭に "method" を付ける
  - tkinter/matplotlibが要求する標準オブジェクト(root, fig, ax, canvasなど)や、
    tkinter.simpledialog.Dialog が要求するbody/apply/__init__のオーバーライドは、
    ライブラリ側の決まりごとなのでリネームしない
  - 画面に表示される文字(ボタン・ダイアログ・メッセージ等のUI)は英語のまま、
    コード中の説明コメントは日本語、という使い分けをしている
"""

import tkinter as tk
from tkinter import ttk, simpledialog, filedialog, messagebox
import matplotlib
matplotlib.use("TkAgg")  # Tkinterのウィンドウの中にmatplotlibのグラフを描けるようにするバックエンド指定

# ---- 日本語/CJKフォント設定 ----
# matplotlibの初期フォント(DejaVu Sans)には日本語のグリフが無いため、
# ユーザーが入力した日本語の信号名などが豆腐(空の四角)になってしまう。
# Windowsに標準で入っている日本語フォントを優先順で指定しておく。
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = ["Meiryo", "Yu Gothic", "MS Gothic", "IPAexGothic", "Noto Sans CJK JP"]
matplotlib.rcParams["axes.unicode_minus"] = False
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # matplotlibのFigureをTkinterに埋め込む部品
from matplotlib.figure import Figure                              # グラフを描く白紙のキャンバス
from matplotlib.patches import FancyBboxPatch, Rectangle, Polygon, FancyArrowPatch  # 図形パーツ一式
from matplotlib.path import Path  # 矢印を独自のベジェ曲線で描くために使う
import json   # 設定の保存/読込(JSON)に使う
import copy   # Undo用に状態を丸ごと複製(deepcopy)するために使う


# ============================================================
# 色のプリセット: RGBを直接打たなくても、名前を選ぶだけで色を変えられるようにする
# 一覧。ここに1行足すだけで、タイマーやバッジで選べる色が増える。
# ============================================================
VAR_COLOR_PALETTE = {
    "Red": "#e74c3c",
    "Pink": "#ff6f61",
    "Orange": "#ff8c42",
    "Yellow": "#f1c40f",
    "Green": "#2ecc71",
    "Blue": "#3498db",
    "Purple": "#7b2fbe",
    "Gray": "#9e9e9e",
}


class VarAddSignalDialog(simpledialog.Dialog):
    """
    「信号を追加」ダイアログ。信号名・種別(digital/data)・所属テキストと
    バッジ色を聞く。simpledialog.Dialogを継承すると、body()で中身の
    ウィジェットを組み立て、OKが押されたらapply()が自動で呼ばれて
    self.result に結果が詰められる、という決まった流れになる。
    """

    def body(self, master):
        ttk.Label(master, text="Signal name").grid(row=0, column=0, sticky="w", pady=3)
        self.varNameEntry = ttk.Entry(master, width=25)
        self.varNameEntry.grid(row=0, column=1, pady=3)

        ttk.Label(master, text="Type").grid(row=1, column=0, sticky="w", pady=3)
        self.varTypeChoice = tk.StringVar(value="digital")
        type_frame = ttk.Frame(master)
        type_frame.grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(type_frame, text="digital / Bit (ON/OFF square wave)", value="digital",
                         variable=self.varTypeChoice).pack(anchor="w")
        ttk.Radiobutton(type_frame, text="data / Word (Data/Clear bus display)", value="data",
                         variable=self.varTypeChoice).pack(anchor="w")

        ttk.Label(master, text="Owner\n(free text, not just PLC/PC)").grid(row=2, column=0, sticky="w", pady=3)
        self.varOwnerEntry = ttk.Entry(master, width=25)
        self.varOwnerEntry.insert(0, "PLC")  # デフォルト値
        self.varOwnerEntry.grid(row=2, column=1, pady=3)

        ttk.Label(master, text="Badge color").grid(row=3, column=0, sticky="w", pady=3)
        self.varColorChoice = tk.StringVar(value="Green")
        color_combo = ttk.Combobox(master, textvariable=self.varColorChoice,
                                    values=list(VAR_COLOR_PALETTE.keys()), state="readonly", width=10)
        color_combo.grid(row=3, column=1, sticky="w", pady=3)

        return self.varNameEntry  # 最初にフォーカスするウィジェット

    def apply(self):
        self.result = {
            "name": self.varNameEntry.get().strip(),
            "type": self.varTypeChoice.get(),
            "owner": self.varOwnerEntry.get().strip(),
            "owner_color": VAR_COLOR_PALETTE[self.varColorChoice.get()],
        }


class VarEditOwnerDialog(simpledialog.Dialog):
    """既存の信号の所属テキストとバッジ色を変更するダイアログ。"""

    def __init__(self, parent, title, current_owner, current_color_name):
        self.varCurrentOwner = current_owner
        self.varCurrentColorName = current_color_name
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Owner (free text, blank = hide badge)").grid(row=0, column=0, sticky="w", pady=3)
        self.varOwnerEntry = ttk.Entry(master, width=25)
        self.varOwnerEntry.insert(0, self.varCurrentOwner)
        self.varOwnerEntry.grid(row=0, column=1, pady=3)

        ttk.Label(master, text="Badge color").grid(row=1, column=0, sticky="w", pady=3)
        self.varColorChoice = tk.StringVar(value=self.varCurrentColorName)
        color_combo = ttk.Combobox(master, textvariable=self.varColorChoice,
                                    values=list(VAR_COLOR_PALETTE.keys()), state="readonly", width=10)
        color_combo.grid(row=1, column=1, sticky="w", pady=3)

        return self.varOwnerEntry

    def apply(self):
        self.result = {
            "owner": self.varOwnerEntry.get().strip(),
            "owner_color": VAR_COLOR_PALETTE[self.varColorChoice.get()],
        }


class VarArrowKindDialog(simpledialog.Dialog):
    """
    矢印を確定する時に出すダイアログ。聞くのは種類(Trigger/Condition)と
    ラベルだけ。色はあえて選択式にしていない(Triggerは常に紫の実線、
    Conditionは常にオレンジの点線という、シンプルな2択のまま)。
    """

    def body(self, master):
        ttk.Label(master, text="Arrow type").grid(row=0, column=0, sticky="w", pady=3)
        self.varKindChoice = tk.StringVar(value="trigger")
        kind_frame = ttk.Frame(master)
        kind_frame.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(kind_frame, text="Trigger (solid line)", value="trigger",
                         variable=self.varKindChoice).pack(anchor="w")
        ttk.Radiobutton(kind_frame, text="Condition (dashed line)", value="condition",
                         variable=self.varKindChoice).pack(anchor="w")

        ttk.Label(master, text="Label (optional)").grid(row=1, column=0, sticky="w", pady=3)
        self.varLabelEntry = ttk.Entry(master, width=20)
        self.varLabelEntry.grid(row=1, column=1, pady=3)
        return None

    def apply(self):
        self.result = {
            "kind": self.varKindChoice.get(),
            "label": self.varLabelEntry.get().strip(),
        }


class VarAddTimerDialog(simpledialog.Dialog):
    """タイマーバー追加ダイアログ。対象信号・範囲・色・ラベルを聞く。"""

    def __init__(self, parent, title, signal_names, max_col):
        self.varSignalNames = signal_names
        self.varMaxCol = max_col
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Target signal").grid(row=0, column=0, sticky="w", pady=3)
        self.varSignalChoice = tk.StringVar(value=self.varSignalNames[0] if self.varSignalNames else "")
        combo = ttk.Combobox(master, textvariable=self.varSignalChoice, values=self.varSignalNames,
                              state="readonly", width=20)
        combo.grid(row=0, column=1, pady=3)

        ttk.Label(master, text="Start column").grid(row=1, column=0, sticky="w", pady=3)
        self.varStartEntry = ttk.Spinbox(master, from_=0, to=max(self.varMaxCol - 1, 0), width=6)
        self.varStartEntry.set(0)
        self.varStartEntry.grid(row=1, column=1, pady=3)

        ttk.Label(master, text="End column").grid(row=2, column=0, sticky="w", pady=3)
        self.varEndEntry = ttk.Spinbox(master, from_=1, to=self.varMaxCol, width=6)
        self.varEndEntry.set(min(3, self.varMaxCol))
        self.varEndEntry.grid(row=2, column=1, pady=3)

        ttk.Label(master, text="Color").grid(row=3, column=0, sticky="w", pady=3)
        self.varColorChoice = tk.StringVar(value="Pink")
        color_combo = ttk.Combobox(master, textvariable=self.varColorChoice,
                                    values=list(VAR_COLOR_PALETTE.keys()), state="readonly", width=10)
        color_combo.grid(row=3, column=1, sticky="w", pady=3)

        ttk.Label(master, text="Label").grid(row=4, column=0, sticky="w", pady=3)
        self.varLabelEntry = ttk.Entry(master, width=20)
        self.varLabelEntry.insert(0, "Timer")
        self.varLabelEntry.grid(row=4, column=1, pady=3)
        return combo

    def apply(self):
        self.result = {
            "signal_name": self.varSignalChoice.get(),
            "start_col": int(self.varStartEntry.get()),
            "end_col": int(self.varEndEntry.get()),
            "color": VAR_COLOR_PALETTE[self.varColorChoice.get()],
            "label": self.varLabelEntry.get().strip(),
        }


class VarManageArrowsDialog(simpledialog.Dialog):
    """
    矢印を一覧から選んで「削除」か「位置編集」ができるダイアログ。
    渡されたリスト(arrows_ref)をコピーではなく参照そのままで受け取り、
    ダイアログ内のボタン操作で直接書き換える方式にしている
    (呼び出し側のTimingChartApp.varArrowsが即座に変わる)。
    """

    def __init__(self, parent, title, arrows_ref, row_count, max_steps):
        self.varArrowsRef = arrows_ref
        self.varRowCount = row_count
        self.varMaxSteps = max_steps
        super().__init__(parent, title)

    def body(self, master):
        self.varListbox = tk.Listbox(master, width=70, height=8)
        self.varListbox.grid(row=0, column=0, columnspan=3, pady=5, padx=5)
        self.methodRefreshList()

        ttk.Button(master, text="Delete selected", command=self.methodDeleteSelected).grid(row=1, column=0, pady=3)
        ttk.Button(master, text="Edit selected position", command=self.methodEditSelected).grid(row=1, column=1, pady=3)
        return None

    def methodRefreshList(self):
        self.varListbox.delete(0, tk.END)
        for i, arrow in enumerate(self.varArrowsRef):
            kind_label = "Trigger" if arrow["kind"] == "trigger" else "Condition"
            start_row, start_x, start_level = arrow["start"]
            end_row, end_x, end_level = arrow["end"]
            self.varListbox.insert(
                tk.END,
                f"{i + 1}: {kind_label}  row {start_row + 1}(x={start_x},{start_level}) -> "
                f"row {end_row + 1}(x={end_x},{end_level})  [{arrow['label']}]"
            )

    def methodDeleteSelected(self):
        selection = self.varListbox.curselection()
        if not selection:
            return
        del self.varArrowsRef[selection[0]]
        self.methodRefreshList()

    def methodEditSelected(self):
        selection = self.varListbox.curselection()
        if not selection:
            return
        arrow = self.varArrowsRef[selection[0]]
        start_row, start_x, start_level = arrow["start"]
        end_row, end_x, end_level = arrow["end"]

        new_start_row = simpledialog.askinteger(
            "Edit", "Start: row number (1-based)", initialvalue=start_row + 1, minvalue=1, maxvalue=self.varRowCount)
        if new_start_row is None:
            return
        new_start_x = simpledialog.askfloat(
            "Edit", f"Start: x position (0-{self.varMaxSteps}, 0.5 steps recommended)", initialvalue=start_x)
        if new_start_x is None:
            return
        new_start_level = simpledialog.askstring(
            "Edit", "Start: level (H = ON corner, L = OFF corner, blank = no level)", initialvalue=start_level or "")
        if new_start_level is None:
            return
        new_end_row = simpledialog.askinteger(
            "Edit", "End: row number (1-based)", initialvalue=end_row + 1, minvalue=1, maxvalue=self.varRowCount)
        if new_end_row is None:
            return
        new_end_x = simpledialog.askfloat(
            "Edit", f"End: x position (0-{self.varMaxSteps}, 0.5 steps recommended)", initialvalue=end_x)
        if new_end_x is None:
            return
        new_end_level = simpledialog.askstring(
            "Edit", "End: level (H = ON corner, L = OFF corner, blank = no level)", initialvalue=end_level or "")
        if new_end_level is None:
            return

        arrow["start"] = (new_start_row - 1, new_start_x, new_start_level.strip().upper() or None)
        arrow["end"] = (new_end_row - 1, new_end_x, new_end_level.strip().upper() or None)
        self.methodRefreshList()

    def apply(self):
        self.result = True  # 変更はボタン操作の時点で即座に反映済み


class VarManageTimersDialog(simpledialog.Dialog):
    """
    VarManageArrowsDialogと同じ考え方で、タイマーバーを個別に
    削除/編集できるダイアログ。「全消去ボタン」は誤操作で全部消えてしまうため廃止しこれに置き換えている。
    """

    def __init__(self, parent, title, timers_ref, max_steps, signal_names):
        self.varTimersRef = timers_ref
        self.varMaxSteps = max_steps
        self.varSignalNames = signal_names
        super().__init__(parent, title)

    def body(self, master):
        self.varListbox = tk.Listbox(master, width=70, height=8)
        self.varListbox.grid(row=0, column=0, columnspan=3, pady=5, padx=5)
        self.methodRefreshList()

        ttk.Button(master, text="Delete selected", command=self.methodDeleteSelected).grid(row=1, column=0, pady=3)
        ttk.Button(master, text="Edit selected", command=self.methodEditSelected).grid(row=1, column=1, pady=3)
        return None

    def methodRefreshList(self):
        self.varListbox.delete(0, tk.END)
        for i, timer in enumerate(self.varTimersRef):
            row_name = self.varSignalNames[timer["row"]] if timer["row"] < len(self.varSignalNames) else "?"
            self.varListbox.insert(
                tk.END, f"{i + 1}: {row_name}  cols {timer['start_col']}-{timer['end_col']}  [{timer['label']}]"
            )

    def methodDeleteSelected(self):
        selection = self.varListbox.curselection()
        if not selection:
            return
        del self.varTimersRef[selection[0]]
        self.methodRefreshList()

    def methodEditSelected(self):
        selection = self.varListbox.curselection()
        if not selection:
            return
        timer = self.varTimersRef[selection[0]]

        new_start = simpledialog.askinteger(
            "Edit", "Start column", initialvalue=timer["start_col"], minvalue=0, maxvalue=max(self.varMaxSteps - 1, 0))
        if new_start is None:
            return
        new_end = simpledialog.askinteger(
            "Edit", "End column", initialvalue=timer["end_col"], minvalue=1, maxvalue=self.varMaxSteps)
        if new_end is None:
            return
        new_label = simpledialog.askstring("Edit", "Label", initialvalue=timer["label"])
        if new_label is None:
            return

        timer["start_col"] = new_start
        timer["end_col"] = new_end
        timer["label"] = new_label
        self.methodRefreshList()

    def apply(self):
        self.result = True


class ToolTip:
    """ボタンにマウスを乗せると説明を出す、小さいツールチップ部品。"""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.methodShowTip)
        widget.bind("<Leave>", self.methodHideTip)

    def methodShowTip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                          background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                          font=("Segoe UI", 9))
        label.pack(ipadx=4, ipady=2)

    def methodHideTip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class TimingChartApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TA_TimingAnalyzer")
        self.root.geometry("1350x820")

        # ============================================================
        # ---- 状態変数("var"接頭辞) ----
        # このアプリの「今の状態」は全部この下の変数に入っている。
        # 保存(JSON)・Undo・描画のどの処理も、これらの変数を読み書きするだけ。
        # ============================================================

        # varSignals: 信号1本(=グラフの1行)ごとの設定。並び順=画面の上から下の順番。
        #   例: {"name":"Request", "type":"digital", "owner":"PLC", "owner_color":"#2ecc71"}
        self.varSignals = []

        # varCellStates: 信号×時刻マスの状態。varSignalsと同じ並び順のリストのリスト。
        #   digital行 -> 各マスが "H"(High/ON) か "L"(Low/OFF)
        #   data行    -> 各マスが表示するテキスト(例 "Data","Clear")
        self.varCellStates = []

        # varCellAnnotations: digital行だけが使う任意の注釈テキスト。波形の高さ自体は
        # 変えず、参考画像の小さいオレンジの"ON"/"OFF"ラベルのような追加情報を乗せる。
        self.varCellAnnotations = []

        # varArrows: Trigger/Condition矢印のリスト(色は種類で固定、選択式ではない)。
        #   "start"/"end" は (行番号, x座標) のタプル。x座標は0.5刻みの小数、
        #   または実際のON/OFF切り替わり位置(角)にスナップした値。
        self.varArrows = []

        # varTimers: 色付きの帯(タイマー)のリスト。
        #   {"row":行番号, "start_col":開始マス, "end_col":終了マス, "color":色コード, "label":文字}
        self.varTimers = []

        # varMarkedColumns: 太字で目立たせている縦線の列番号を集めたset(集合)。
        self.varMarkedColumns = set()

        # varNoteText: チャートの下に表示する1行の自由メモ(参考画像の下にある
        # キャプションのようなもの)。
        self.varNoteText = ""

        # varTimeSteps: 横方向(時間軸)のマス数
        self.varTimeSteps = 15

        # varArrowModeActive: Trueの間はセルクリックが無効になり、代わりに
        # グリッド上にスナップ可能な点がドットで表示され、
        # 「始点ドットをクリック→終点ドットをクリック」の2ステップで
        # 矢印を作る(ドラッグではなくクリック→クリック方式)。
        self.varArrowModeActive = False
        # varArrowModeStartPoint: Arrow Mode中に選んだ「始点」の
        # (行番号, x座標, レベル"H"/"L"/None) のタプル。まだ何も選んでいなければNone。
        self.varArrowModeStartPoint = None

        # varUndoStack / varRedoStack: 元に戻す/やり直す用に、状態のスナップショット
        # (丸ごとコピー)を積んでおくスタック。
        self.varUndoStack = []
        self.varRedoStack = []

        self.methodBuildInitialRows()
        self.methodBuildToolbar()
        self.methodBuildCanvas()
        self.methodRedraw()

    # ============================================================
    # 起動時に最初から10行を用意しておく
    # ============================================================
    def methodBuildInitialRows(self):
        for i in range(1, 11):
            # 最初の5行はTechnoalpha PLC(緑)、残り5行はPeritec PC(青)をデフォルト所属にする
            # どうせペリテックとのやり取りでしかつかわないでしょう。。。
            if i <= 5:
                owner_text = "Technoalpha PLC"
                owner_color = VAR_COLOR_PALETTE["Green"]
            else:
                owner_text = "Peritec PC"
                owner_color = VAR_COLOR_PALETTE["Blue"]

            self.varSignals.append({
                "name": f"Signal{i}", "type": "digital", "owner": owner_text,
                "owner_color": owner_color,
            })
            self.varCellStates.append(["L"] * self.varTimeSteps)
            self.varCellAnnotations.append([""] * self.varTimeSteps)

    # ============================================================
    # ツールバー(画面上部のボタン一式)を作る
    # ============================================================
    def methodBuildToolbar(self):
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # 各ボタンは「作る→配置(pack)→ツールチップを付ける」の3点セット。
        # command=self.method〜 の部分で「押されたらどの関数を呼ぶか」を指定している。

        add_signal_button = ttk.Button(toolbar, text="Add Signal", command=self.methodAddSignal)
        add_signal_button.pack(side=tk.LEFT, padx=3)
        ToolTip(add_signal_button, "Add a new signal row. Use this once 10 rows aren't enough.")

        undo_button = ttk.Button(toolbar, text="Undo", command=self.methodUndo)
        undo_button.pack(side=tk.LEFT, padx=3)
        ToolTip(undo_button, "Undo the last change (up to 20 steps).")

        redo_button = ttk.Button(toolbar, text="Redo", command=self.methodRedo)
        redo_button.pack(side=tk.LEFT, padx=3)
        ToolTip(redo_button, "Redo a change that was undone. A new edit clears the redo history.")

        ttk.Label(toolbar, text="  Time steps:").pack(side=tk.LEFT)
        self.varTimeStepsEntry = ttk.Spinbox(toolbar, from_=3, to=40, width=5)
        self.varTimeStepsEntry.set(self.varTimeSteps)
        self.varTimeStepsEntry.pack(side=tk.LEFT, padx=3)
        apply_steps_button = ttk.Button(toolbar, text="Apply", command=self.methodApplyTimeSteps)
        apply_steps_button.pack(side=tk.LEFT, padx=3)
        ToolTip(apply_steps_button, "Change the number of time columns to the value on the left.")

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.varArrowModeButton = ttk.Button(toolbar, text="Arrow Mode: OFF", command=self.methodToggleArrowMode)
        self.varArrowModeButton.pack(side=tk.LEFT, padx=3)
        ToolTip(self.varArrowModeButton,
                "Turn on to place arrows by clicking two dots (start, then end) instead of dragging.\n"
                "Right-click cancels the start point you just picked.")

        manage_arrows_button = ttk.Button(toolbar, text="Manage Arrows", command=self.methodManageArrows)
        manage_arrows_button.pack(side=tk.LEFT, padx=3)
        ToolTip(manage_arrows_button, "Pick an arrow from a list to move or delete it individually.")

        clear_arrows_button = ttk.Button(toolbar, text="Clear All Arrows", command=self.methodClearArrows)
        clear_arrows_button.pack(side=tk.LEFT, padx=3)
        ToolTip(clear_arrows_button, "Remove every arrow (Trigger and Condition) at once.")

        add_timer_button = ttk.Button(toolbar, text="Add Timer Bar", command=self.methodAddTimer)
        add_timer_button.pack(side=tk.LEFT, padx=3)
        ToolTip(add_timer_button, "Add a colored bar (like an equipment timer) over a chosen signal and range.")

        manage_timers_button = ttk.Button(toolbar, text="Manage Timers", command=self.methodManageTimers)
        manage_timers_button.pack(side=tk.LEFT, padx=3)
        ToolTip(manage_timers_button, "Pick a timer bar from a list to edit or delete it individually.")

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        edit_note_button = ttk.Button(toolbar, text="Edit Note", command=self.methodEditNote)
        edit_note_button.pack(side=tk.LEFT, padx=3)
        ToolTip(edit_note_button, "Set the one-line note shown under the chart (leave blank to remove it).")

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        save_json_button = ttk.Button(toolbar, text="Save (JSON)", command=self.methodSaveJson)
        save_json_button.pack(side=tk.LEFT, padx=3)
        ToolTip(save_json_button, "Save the whole chart to a JSON file so you can reopen and keep editing later.")

        load_json_button = ttk.Button(toolbar, text="Load (JSON)", command=self.methodLoadJson)
        load_json_button.pack(side=tk.LEFT, padx=3)
        ToolTip(load_json_button, "Load a previously saved JSON file.")

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        export_png_button = ttk.Button(toolbar, text="Export PNG (for Excel/PPT)", command=self.methodExportPng)
        export_png_button.pack(side=tk.LEFT, padx=3)
        ToolTip(export_png_button, "Save the chart as a high-resolution PNG ready to paste into Excel or PowerPoint.")

        hint_text = (
            "Grid left click = toggle ON/OFF or Data/Clear   |   Grid right click = edit text   |   Arrow Mode button = click a start dot then an end dot to place an arrow\n"
            "Click the \"Timing chart\" header strip = toggle a bold marker on the nearest vertical line   |   Click a signal name = rename   |   Click a badge = change owner/color   |   Right-click a signal name = duplicate/delete"
        )
        hint_label = ttk.Label(self.root, text=hint_text, foreground="#555555", justify=tk.LEFT)
        hint_label.pack(side=tk.TOP, anchor="w", padx=8)

    # ============================================================
    # matplotlibの描画領域をTkinterに埋め込む
    # ============================================================
    def methodBuildCanvas(self):
        self.fig = Figure(figsize=(11, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # mpl_connect: 「このイベントが起きたらこの関数を呼ぶ」という登録。
        # クリック操作は全部button_press_event(マウスを押した瞬間)だけで処理する
        # (Arrow Mode導入前はドラッグ判定のためbutton_release_eventも使っていたが、
        #  クリック→クリック方式に変えたことで不要になった)。
        self.canvas.mpl_connect("button_press_event", self.methodOnPress)

    # ============================================================
    # Undo / Redo
    # 「差分」ではなく「状態を丸ごとコピーして保存→戻す時は丸ごと置き換える」
    # という、一番単純な方式にしている(その分メモリは使うがバグが起きにくい)。
    # ============================================================
    def methodCaptureSnapshot(self):
        # deepcopyを使うのは、普通に代入すると「同じ実体を指すコピー」になり、
        # 後で元データを書き換えるとスナップショットまで一緒に変わってしまうため。
        return {
            "varSignals": copy.deepcopy(self.varSignals),
            "varCellStates": copy.deepcopy(self.varCellStates),
            "varCellAnnotations": copy.deepcopy(self.varCellAnnotations),
            "varArrows": copy.deepcopy(self.varArrows),
            "varTimers": copy.deepcopy(self.varTimers),
            "varMarkedColumns": copy.deepcopy(self.varMarkedColumns),
            "varNoteText": self.varNoteText,
            "varTimeSteps": self.varTimeSteps,
        }

    def methodRestoreSnapshot(self, snapshot):
        self.varSignals = snapshot["varSignals"]
        self.varCellStates = snapshot["varCellStates"]
        self.varCellAnnotations = snapshot["varCellAnnotations"]
        self.varArrows = snapshot["varArrows"]
        self.varTimers = snapshot["varTimers"]
        self.varMarkedColumns = snapshot["varMarkedColumns"]
        self.varNoteText = snapshot["varNoteText"]
        self.varTimeSteps = snapshot["varTimeSteps"]
        self.varTimeStepsEntry.set(self.varTimeSteps)
        self.methodRedraw()

    def methodPushUndoSnapshot(self):
        # 何かを変更する「直前」に必ずこれを呼ぶ、というルールで各所に仕込んである。
        self.varUndoStack.append(self.methodCaptureSnapshot())
        if len(self.varUndoStack) > 20:
            self.varUndoStack.pop(0)  # 20件を超えたら一番古いものを捨てる
        self.varRedoStack = []  # 新しい変更をしたら、それより後のRedo履歴は意味を失う

    def methodUndo(self):
        if not self.varUndoStack:
            messagebox.showinfo("Undo", "Nothing left to undo.")
            return
        self.varRedoStack.append(self.methodCaptureSnapshot())
        snapshot = self.varUndoStack.pop()
        self.methodRestoreSnapshot(snapshot)

    def methodRedo(self):
        if not self.varRedoStack:
            messagebox.showinfo("Redo", "Nothing to redo.")
            return
        self.varUndoStack.append(self.methodCaptureSnapshot())
        snapshot = self.varRedoStack.pop()
        self.methodRestoreSnapshot(snapshot)

    def methodToggleArrowMode(self):
        self.varArrowModeActive = not self.varArrowModeActive
        self.varArrowModeStartPoint = None  # モードが切り替わったら選択中の始点はリセット
        self.varArrowModeButton.config(text=f"Arrow Mode: {'ON' if self.varArrowModeActive else 'OFF'}")
        self.methodRedraw()

    # ============================================================
    # 「Add Signal」ボタンの処理
    # ============================================================
    def methodAddSignal(self):
        dialog = VarAddSignalDialog(self.root, title="Add Signal")
        result = dialog.result
        if not result:
            return  # Cancelされた場合は何もしない
        if not result["name"]:
            messagebox.showwarning("Input error", "Please enter a signal name. Nothing was added.")
            return

        self.methodPushUndoSnapshot()
        self.varSignals.append({
            "name": result["name"], "type": result["type"],
            "owner": result["owner"], "owner_color": result["owner_color"],
        })
        default_state = "L" if result["type"] == "digital" else "Data"
        self.varCellStates.append([default_state] * self.varTimeSteps)
        self.varCellAnnotations.append([""] * self.varTimeSteps)
        self.methodRedraw()

    # 時間マス数(横方向の分割数)をSpinboxの値で更新する
    def methodApplyTimeSteps(self):
        try:
            new_steps = int(self.varTimeStepsEntry.get())
        except ValueError:
            messagebox.showwarning("Input error", "Please enter a number.")
            return

        self.methodPushUndoSnapshot()

        for row_index, row_states in enumerate(self.varCellStates):
            if new_steps > len(row_states):
                # マスが増える場合: 直前の状態を引き継いで埋める(急に無地になると変なので)
                fill_value = row_states[-1] if row_states else (
                    "L" if self.varSignals[row_index]["type"] == "digital" else "Data"
                )
                row_states.extend([fill_value] * (new_steps - len(row_states)))
            elif new_steps < len(row_states):
                # マスが減る場合: はみ出た分を後ろから切り捨てる
                del row_states[new_steps:]

            annotation_row = self.varCellAnnotations[row_index]
            if new_steps > len(annotation_row):
                annotation_row.extend([""] * (new_steps - len(annotation_row)))
            elif new_steps < len(annotation_row):
                del annotation_row[new_steps:]

        self.varTimeSteps = new_steps
        # マス数が減った時、範囲外を指してしまうマーク列やタイマーを掃除する
        self.varMarkedColumns = {c for c in self.varMarkedColumns if c <= self.varTimeSteps}
        self.varTimers = [t for t in self.varTimers if t["end_col"] <= self.varTimeSteps]
        self.methodRedraw()

    def methodClearArrows(self):
        self.methodPushUndoSnapshot()
        self.varArrows = []
        self.methodRedraw()

    def methodManageArrows(self):
        if not self.varArrows:
            messagebox.showinfo("Manage Arrows", "There are no arrows yet.")
            return
        self.methodPushUndoSnapshot()  # ダイアログ内で直接データを書き換えるので、開く前に保存しておく
        VarManageArrowsDialog(self.root, "Manage Arrows", self.varArrows, len(self.varSignals), self.varTimeSteps)
        self.methodRedraw()

    def methodManageTimers(self):
        if not self.varTimers:
            messagebox.showinfo("Manage Timers", "There are no timer bars yet.")
            return
        self.methodPushUndoSnapshot()
        names = [s["name"] for s in self.varSignals]
        VarManageTimersDialog(self.root, "Manage Timers", self.varTimers, self.varTimeSteps, names)
        self.methodRedraw()

    # ============================================================
    # タイマーバー追加
    # ============================================================
    def methodAddTimer(self):
        if not self.varSignals:
            messagebox.showwarning("Error", "There are no signals yet.")
            return

        names = [s["name"] for s in self.varSignals]
        dialog = VarAddTimerDialog(self.root, "Add Timer Bar", names, self.varTimeSteps)
        result = dialog.result
        if not result:
            return
        if result["end_col"] <= result["start_col"]:
            messagebox.showwarning("Input error", "End column must come after start column.")
            return

        row_index = next((i for i, s in enumerate(self.varSignals) if s["name"] == result["signal_name"]), None)
        if row_index is None:
            return

        self.methodPushUndoSnapshot()
        self.varTimers.append({
            "row": row_index,
            "start_col": result["start_col"],
            "end_col": result["end_col"],
            "color": result["color"],
            "label": result["label"],
        })
        self.methodRedraw()

    # ============================================================
    # チャート下の自由メモ
    # ============================================================
    def methodEditNote(self):
        new_note = simpledialog.askstring(
            "Edit Note", "Note shown below the chart (blank to remove):", initialvalue=self.varNoteText
        )
        if new_note is not None:
            self.methodPushUndoSnapshot()
            self.varNoteText = new_note
            self.methodRedraw()

    # ============================================================
    # マウスを押した瞬間の処理(すべてのクリック操作の入口)
    # ============================================================
    def methodOnPress(self, event):
        if event.xdata is None or event.ydata is None:
            return
        if not self.varSignals:
            return
        if event.dblclick:
            # matplotlibはダブルクリック時に「1発目」→「2発目(dblclick=True)」の
            # 順で2回イベントを出す。両方処理するとトグルが2回走って
            # 元に戻ってしまう(何も起きていないように見える)ので、2発目は無視する。
            return

        # ---- Arrow Modeが有効な間は、他の操作は全部無効にしてクリックを
        #      矢印の始点/終点選択だけに使う(誤操作防止のため意図的な仕様) ----
        if self.varArrowModeActive:
            self.methodHandleArrowModeClick(event)
            return

        row_count = len(self.varSignals)

        # ---- ヘッダ帯(「Timing chart」の文字がある行)をクリックした場合 ----
        if event.ydata >= row_count + 0.3:
            if event.button == 1 and 0 <= event.xdata <= self.varTimeSteps:
                self.methodToggleMarkedColumn(round(event.xdata))
            return

        row_index = self.methodPickRow(event.ydata)
        if row_index is None:
            return

        # ---- 時間グリッドより左側の「ラベル領域」(信号名・バッジ)をクリックした場合 ----
        if event.xdata < 0:
            self.methodHandleLabelClick(event, row_index)
            return

        # ---- ここまで来たら時間グリッド本体 ----
        col_index = int(event.xdata)
        if col_index < 0 or col_index >= self.varTimeSteps:
            return

        if event.button == 1:
            self.methodToggleCellState(row_index, col_index)
            self.methodRedraw()
        elif event.button == 3:
            self.methodEditCellText(row_index, col_index)
            self.methodRedraw()

    def methodPickRow(self, ydata):
        row_count = len(self.varSignals)
        # 信号は上から順に並んでいて、y座標は下がゼロ・上に行くほど大きい値になっているので、
        # 「行数-y座標」を整数に切り捨てると「上から何番目か(0始まり)」が求まる
        row_from_top = int(row_count - ydata)
        if row_from_top < 0 or row_from_top >= row_count:
            return None
        return row_from_top

    # ============================================================
    # Arrow Mode: 始点ドットをクリック→終点ドットをクリックの2ステップで矢印を作る。
    # ドラッグ方式だと離す場所を誤りやすい(ミスが多い)という指摘を受けて、
    # 1回ずつ確実にクリックする方式に変更した。
    # ============================================================
    def methodHandleArrowModeClick(self, event):
        if event.button == 3:
            # 右クリックで、選択中の始点をキャンセルする
            if self.varArrowModeStartPoint is not None:
                self.varArrowModeStartPoint = None
                self.methodRedraw()
            return
        if event.button != 1:
            return

        picked = self.methodPickNearestSnapPoint(event.xdata, event.ydata)
        if picked is None:
            return
        row_index, x_pos, level = picked

        if self.varArrowModeStartPoint is None:
            # 1回目のクリック: このドットを始点として記憶し、赤く強調表示する
            self.varArrowModeStartPoint = (row_index, x_pos, level)
            self.methodRedraw()
        else:
            # 2回目のクリック: 記憶していた始点とこのドットの間に矢印を確定する
            start_row, start_x, start_level = self.varArrowModeStartPoint
            self.varArrowModeStartPoint = None
            self.methodCreateArrowByDrag(start_row, start_x, start_level, row_index, x_pos, level)
            self.methodRedraw()

    # ある行でドットとして表示される(=クリックで選べる)点を全部リストアップする。
    # 戻り値は (x座標, レベル) のタプルのリスト。レベルは digital行では "H"(ONの角/頂点)
    # か "L"(OFFの角/底辺)、data行では None(高さの区別が無いので中央固定)。
    #
    # 切り替わりの境界(角)には、上端(ONの角)と下端(OFFの角)の2点を別々に用意している。
    # 境界を挟む縦線は実際にHighの高さからLowの高さまで伸びているので、その両端どちらも
    # 矢印の目的地として選べるようにする、という考え方。
    def methodListSnapCandidates(self, row_index):
        signal = self.varSignals[row_index]
        states = self.varCellStates[row_index]
        n = len(states)

        if signal["type"] == "digital":
            candidates = set()
            # 行の一番左端/右端は、その端の実際の状態1点だけを候補にする
            if n > 0:
                candidates.add((0.0, states[0]))
                candidates.add((float(n), states[n - 1]))
            # 内部の切り替わり境界: ONの角(H)とOFFの角(L)を両方候補にする
            for col in range(1, n):
                if states[col] != states[col - 1]:
                    candidates.add((float(col), "H"))
                    candidates.add((float(col), "L"))
            # 各マスの中間点: そのマス自身の状態1点だけ
            for col in range(n):
                candidates.add((col + 0.5, states[col]))
            return sorted(candidates, key=lambda pair: (pair[0], pair[1]))

        return [(c * 0.5, None) for c in range(0, n * 2 + 1)]

    # クリック位置から「何行目か」を求め、その行の中で実際の見た目の位置
    # (x座標とH/Lの高さ)が一番近いドットを1つ選ぶ。同じx座標でもH/Lで
    # 見た目の高さが違うので、x距離だけでなく実際のy座標との距離で比べる。
    def methodPickNearestSnapPoint(self, xdata, ydata):
        row_index = self.methodPickRow(ydata)
        if row_index is None:
            return None
        candidates = self.methodListSnapCandidates(row_index)
        if not candidates:
            return None

        row_count = len(self.varSignals)
        top_y = row_count - row_index
        best_candidate = None
        best_distance = None
        for x, level in candidates:
            y = self.methodComputeArrowY(row_index, top_y, level)
            distance = (x - xdata) ** 2 + (y - ydata) ** 2
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_candidate = (x, level)

        x_pos, level = best_candidate
        return (row_index, x_pos, level)

    def methodToggleMarkedColumn(self, col_boundary):
        self.methodPushUndoSnapshot()
        if col_boundary in self.varMarkedColumns:
            self.varMarkedColumns.remove(col_boundary)
        else:
            self.varMarkedColumns.add(col_boundary)
        self.methodRedraw()

    # ============================================================
    # 左側ラベル領域(信号名・バッジ)のクリック処理
    # ============================================================
    def methodHandleLabelClick(self, event, row_index):
        if event.button == 1:
            # バッジ(x=-5.0あたりから開始)と信号名(左端寄り)の間で判定を分ける
            if event.xdata >= -5.3:
                self.methodEditOwnerBadge(row_index)
            else:
                self.methodRenameSignal(row_index)
        elif event.button == 3:
            self.methodShowRowContextMenu(event, row_index)

    def methodRenameSignal(self, row_index):
        current = self.varSignals[row_index]["name"]
        new_name = simpledialog.askstring("Rename Signal", "New signal name:", initialvalue=current)
        if new_name:
            self.methodPushUndoSnapshot()
            self.varSignals[row_index]["name"] = new_name
            self.methodRedraw()

    def methodEditOwnerBadge(self, row_index):
        current_owner = self.varSignals[row_index]["owner"]
        current_color_hex = self.varSignals[row_index].get("owner_color", VAR_COLOR_PALETTE["Green"])
        # 今の色コードから対応する色名を逆引きして、ダイアログを開いた時に正しい選択肢が出るようにする
        current_color_name = next(
            (name for name, hex_value in VAR_COLOR_PALETTE.items() if hex_value == current_color_hex), "Green"
        )

        dialog = VarEditOwnerDialog(self.root, "Change Owner", current_owner, current_color_name)
        result = dialog.result
        if result is not None:
            self.methodPushUndoSnapshot()
            self.varSignals[row_index]["owner"] = result["owner"]
            self.varSignals[row_index]["owner_color"] = result["owner_color"]
            self.methodRedraw()

    def methodShowRowContextMenu(self, event, row_index):
        signal_name = self.varSignals[row_index]["name"]
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"Duplicate '{signal_name}'", command=lambda: self.methodDuplicateRow(row_index))
        menu.add_command(label=f"Delete '{signal_name}'", command=lambda: self.methodDeleteRow(row_index))
        try:
            # event.guiEvent は本物のTkinterイベント。x_root/y_rootで画面全体の座標が取れる。
            menu.tk_popup(event.guiEvent.x_root, event.guiEvent.y_root)
        finally:
            menu.grab_release()

    def methodDuplicateRow(self, row_index):
        self.methodPushUndoSnapshot()

        new_signal = copy.deepcopy(self.varSignals[row_index])
        new_signal["name"] = new_signal["name"] + "_copy"
        new_states = copy.deepcopy(self.varCellStates[row_index])
        new_annotations = copy.deepcopy(self.varCellAnnotations[row_index])

        insert_at = row_index + 1
        self.varSignals.insert(insert_at, new_signal)
        self.varCellStates.insert(insert_at, new_states)
        self.varCellAnnotations.insert(insert_at, new_annotations)

        # 行を1本挿入すると、それより下の行は全部1つ下にズレる。矢印/タイマーは
        # 「何行目」という番号で信号を覚えているので、挿入位置以降を指していた
        # ものは行番号を+1して補正する。
        for arrow in self.varArrows:
            arrow["start"] = self.methodShiftArrowRowIndex(arrow["start"], insert_at, +1, inclusive=True)
            arrow["end"] = self.methodShiftArrowRowIndex(arrow["end"], insert_at, +1, inclusive=True)
        for timer in self.varTimers:
            if timer["row"] >= insert_at:
                timer["row"] += 1

        self.methodRedraw()

    def methodDeleteRow(self, row_index):
        signal_name = self.varSignals[row_index]["name"]
        if not messagebox.askyesno("Confirm", f"Delete '{signal_name}'?"):
            return

        self.methodPushUndoSnapshot()

        del self.varSignals[row_index]
        del self.varCellStates[row_index]
        del self.varCellAnnotations[row_index]

        # 削除した行を指していた矢印は意味が無いので消す。それ以外の、削除位置より
        # 後ろを指していた矢印は行番号を-1して補正する(複製の時と逆の処理)。
        new_arrows = []
        for arrow in self.varArrows:
            if arrow["start"][0] == row_index or arrow["end"][0] == row_index:
                continue
            arrow["start"] = self.methodShiftArrowRowIndex(arrow["start"], row_index, -1, inclusive=False)
            arrow["end"] = self.methodShiftArrowRowIndex(arrow["end"], row_index, -1, inclusive=False)
            new_arrows.append(arrow)
        self.varArrows = new_arrows

        new_timers = []
        for timer in self.varTimers:
            if timer["row"] == row_index:
                continue
            if timer["row"] > row_index:
                timer["row"] -= 1
            new_timers.append(timer)
        self.varTimers = new_timers

        self.methodRedraw()

    # 行の挿入/削除で矢印が指す行番号がズレるのを補正する共通処理(x位置・レベルはそのまま)
    # inclusive=True  : 挿入用。compare以上(その行自身も含む)なら動かす
    # inclusive=False : 削除用。compareより後ろだけ動かす(その行自身は既に別処理で消えている)
    def methodShiftArrowRowIndex(self, point, compare, delta, inclusive):
        row, x, level = point
        if (inclusive and row >= compare) or (not inclusive and row > compare):
            row += delta
        return (row, x, level)

    # ============================================================
    # 時間グリッドのセル操作
    # ============================================================
    def methodToggleCellState(self, row_index, col_index):
        self.methodPushUndoSnapshot()
        signal = self.varSignals[row_index]
        current = self.varCellStates[row_index][col_index]

        if signal["type"] == "digital":
            self.varCellStates[row_index][col_index] = "L" if current == "H" else "H"
        else:
            preset_cycle = {"Data": "Clear", "Clear": "Data"}
            self.varCellStates[row_index][col_index] = preset_cycle.get(current, "Data")

    def methodEditCellText(self, row_index, col_index):
        signal = self.varSignals[row_index]

        if signal["type"] == "data":
            current_text = self.varCellStates[row_index][col_index]
            new_text = simpledialog.askstring(
                "Edit Text", "Text to display in this cell:", initialvalue=current_text
            )
            if new_text is not None:
                self.methodPushUndoSnapshot()
                self.varCellStates[row_index][col_index] = new_text
        else:
            current_text = self.varCellAnnotations[row_index][col_index]
            new_text = simpledialog.askstring(
                "Annotation Text", "Annotation to attach at this timing (e.g. ON, OFF. Blank to remove):",
                initialvalue=current_text
            )
            if new_text is not None:
                self.methodPushUndoSnapshot()
                self.varCellAnnotations[row_index][col_index] = new_text

    def methodCreateArrowByDrag(self, start_row, start_x, start_level, end_row, end_x, end_level):
        dialog = VarArrowKindDialog(self.root, title="Create Arrow")
        result = dialog.result
        if not result:
            return

        self.methodPushUndoSnapshot()
        self.varArrows.append({
            "kind": result["kind"],
            "start": (start_row, start_x, start_level),
            "end": (end_row, end_x, end_level),
            "label": result["label"],
        })

    # ============================================================
    # 図全体を再描画する
    # ============================================================
    def methodRedraw(self):
        self.ax.clear()
        self.methodDrawChart(self.ax)
        self.canvas.draw()

    # 外枠の罫線と、「Signal」列と「Timing chart」列を区切る縦線、
    # ヘッダ内の区切り線(タイトルと列番号の間)、各信号行同士を区切る薄いグレーの
    # 横線を描く。上端は「Timing chart」の文字にかぶらないよう、文字の上端より
    # さらに上に余白を取ってから線を引いている(以前は文字とかぶってしまっていた)。
    def methodDrawTableBorder(self, ax, row_count):
        left = self.varLabelAreaLeft
        right = self.varTimeSteps
        top = row_count + 1.25
        bottom = -0.35
        title_divider = row_count + 0.75   # タイトル文字と列番号を区切るグレー線
        header_bottom = row_count + 0.3    # 列番号と1行目の信号を区切る黒線

        # 外枠(四角形を1本の折れ線として描く)
        ax.plot([left, right, right, left, left], [bottom, bottom, top, top, bottom],
                color="black", linewidth=1.2, zorder=1, clip_on=False)
        # タイトル文字("Signal"/"Timing chart")と列番号を区切る薄いグレー線
        ax.plot([left, right], [title_divider, title_divider], color="#cccccc", linewidth=0.8, zorder=1)
        # 列番号と1行目の信号を区切る黒い横線
        ax.plot([left, right], [header_bottom, header_bottom], color="black", linewidth=1.2, zorder=1)
        # 「Signal」列と「Timing chart」列を区切る縦線
        ax.plot([0, 0], [bottom, top], color="black", linewidth=1.2, zorder=1, clip_on=False)

        # 信号1行ごとの境界に、薄いグレーの横線を引く
        for row_index in range(1, row_count):
            y = row_count - row_index
            ax.plot([left, right], [y, y], color="#cccccc", linewidth=0.8, zorder=1)

    # 長い信号名/所属名をフォントサイズはそのままに2行へ折り返す。
    # 「文字サイズは変えず、幅を広げて」という要望だが、幅を無限に取ると今度は
    # 肝心のタイミングチャート本体が見えなくなるので、一定の長さを超えたら
    # スペースの近くで2行に分割する、という現実的な落とし所にしている。
    # (スペースが無い/見つからない場合は文字数のちょうど半分で強制的に分割する)
    def methodWrapLongLabel(self, text, threshold=13):
        if len(text) <= threshold:
            return text

        mid = len(text) // 2
        left_space = text.rfind(" ", 0, mid)
        right_space = text.find(" ", mid)

        if left_space == -1 and right_space == -1:
            split_at = mid
            return text[:split_at] + "\n" + text[split_at:]

        if left_space == -1:
            split_at = right_space
        elif right_space == -1:
            split_at = left_space
        else:
            # 中央に近い方のスペースを選ぶ
            split_at = left_space if (mid - left_space) <= (right_space - mid) else right_space

        return text[:split_at].rstrip() + "\n" + text[split_at:].lstrip()

    # 実際の描画処理。画面表示・PNG出力のどちらもこの関数を呼ぶので、
    # 見た目が2つの間でズレることがない。
    def methodDrawChart(self, ax):
        row_count = len(self.varSignals)
        # varLabelAreaLeft: 信号名/バッジのために左側に確保する余白。
        # 「ワークサイドクランプ X軸 パーティクル吸引ON」のような長めの文字列を
        # 実際にmatplotlibで測ってみたところ11pt・CJKフォントで幅9ユニット超と
        # かなり広いため、無制限には広げず、2行折り返しと組み合わせて現実的な幅にした。
        self.varLabelAreaLeft = -9.6
        name_x = self.varLabelAreaLeft + 0.1
        badge_x = -5.0
        ax.set_xlim(self.varLabelAreaLeft, self.varTimeSteps + 2.2)
        ax.set_ylim(-1.0, row_count + 1.35)
        ax.axis("off")

        if row_count == 0:
            ax.text(2, 0.5, "Use 'Add Signal' to add a row", fontsize=12)
            return

        # ---- 外枠の罫線と、項目列/Timing chart列を区切る縦線 ----
        self.methodDrawTableBorder(ax, row_count)

        # ---- 縦の目盛線: マークした列は少し濃い緑の点線、それ以外は薄い点線 ----
        for col in range(self.varTimeSteps + 1):
            if col in self.varMarkedColumns:
                ax.plot([col, col], [-0.3, row_count + 0.5], linestyle=":", color="#2e7d32", linewidth=1.3, zorder=0)
            else:
                ax.plot([col, col], [-0.3, row_count + 0.5], linestyle=":", color="#8fd19e", linewidth=0.8, zorder=0)

        ax.text((self.varTimeSteps) / 2, row_count + 1.0, "Timing chart", fontsize=13, ha="center", va="center")
        ax.text((self.varLabelAreaLeft) / 2, row_count + 1.0, "Signal", fontsize=12, fontweight="bold",
                ha="center", va="center")

        # ---- 列番号(1, 2, 3...): タイトルとの区切り線の下、1行目の信号の上に振る ----
        for col in range(self.varTimeSteps):
            ax.text(col + 0.5, row_count + 0.52, str(col + 1), fontsize=7, ha="center",
                    va="center", color="#888888")

        for row_index, signal in enumerate(self.varSignals):
            top_y = row_count - row_index
            row_state_list = self.varCellStates[row_index]

            # 信号名: フォントサイズは固定(11pt)のまま、長ければ2行に折り返す
            name_text = self.methodWrapLongLabel(signal["name"])
            ax.text(name_x, top_y - 0.5, name_text, fontsize=11, va="center")

            owner_text = signal["owner"]
            if owner_text:
                color = signal.get("owner_color") or {"PLC": "#2ecc71", "PC": "#3498db"}.get(owner_text, "#9e9e9e")
                self.methodDrawBadge(ax, badge_x, top_y - 0.68, owner_text, color)

            if signal["type"] == "digital":
                self.methodDrawDigitalRow(ax, top_y, row_state_list, self.varCellAnnotations[row_index])
            else:
                self.methodDrawDataRow(ax, top_y, row_state_list)

        for timer in self.varTimers:
            self.methodDrawTimer(ax, timer, row_count)

        for arrow in self.varArrows:
            self.methodDrawArrow(ax, arrow, row_count)

        if self.varArrowModeActive:
            self.methodDrawArrowModeDots(ax, row_count)

        self.methodDrawLegend(ax, row_count)

        if self.varNoteText:
            ax.text(self.varLabelAreaLeft + 0.1, -0.65, self.varNoteText, fontsize=9, ha="left")

    def methodDrawBadge(self, ax, x, y, text, color):
        width = max(0.5, 0.12 * len(text) + 0.25)  # 文字が長いほど横幅を自動で広げる
        box = FancyBboxPatch((x, y), width, 0.3,
                              boxstyle="round,pad=0.02",
                              linewidth=0, facecolor=color, zorder=3)
        ax.add_patch(box)
        ax.text(x + width / 2, y + 0.15, text, fontsize=7, color="white",
                ha="center", va="center", zorder=4)

    def methodDrawDigitalRow(self, ax, top_y, row_state_list, annotation_list):
        low_y = top_y - 0.75   # Low(OFF)の高さ
        high_y = top_y - 0.35  # High(ON)の高さ
        n = len(row_state_list)

        for col in range(n):
            y = high_y if row_state_list[col] == "H" else low_y
            ax.plot([col, col + 1], [y, y], color="black", linewidth=1.4, zorder=2)

            # 1つ前のマスと高さが違えば、境目に縦線を引いて「階段状」の波形にする
            if col > 0:
                prev_y = high_y if row_state_list[col - 1] == "H" else low_y
                if prev_y != y:
                    ax.plot([col, col], [prev_y, y], color="black", linewidth=1.4, zorder=2)

            annotation_text = annotation_list[col] if col < len(annotation_list) else ""
            if annotation_text:
                ax.text(col + 0.15, top_y - 0.12, annotation_text, fontsize=7, color="white",
                        ha="center", va="center", zorder=4,
                        bbox=dict(boxstyle="round,pad=0.15", facecolor="#ff8c42", edgecolor="none"))

    def methodDrawDataRow(self, ax, top_y, row_state_list):
        band_bottom = top_y - 0.85
        band_top = top_y - 0.35
        band_mid = (band_bottom + band_top) / 2
        slant = 0.15  # 区間の境目を斜めにカットする量
        n = len(row_state_list)

        # 連続して同じ値のマスを1つの「区間」にまとめる
        segments = []
        seg_start = 0
        for col in range(1, n + 1):
            if col == n or row_state_list[col] != row_state_list[seg_start]:
                segments.append((seg_start, col, row_state_list[seg_start]))
                seg_start = col

        for seg_index, (s, e, text) in enumerate(segments):
            x0, x1 = float(s), float(e)
            left_flat = (seg_index == 0)                  # 一番左の区間か(左端は斜めにしない)
            right_flat = (seg_index == len(segments) - 1)  # 一番右の区間か(右端は斜めにしない)

            if left_flat and right_flat:
                points = [(x0, band_bottom), (x0, band_top), (x1, band_top), (x1, band_bottom)]
            elif left_flat:
                points = [(x0, band_bottom), (x0, band_top), (x1 - slant, band_top),
                          (x1, band_mid), (x1 - slant, band_bottom)]
            elif right_flat:
                points = [(x0, band_mid), (x0 + slant, band_top), (x1, band_top),
                          (x1, band_bottom), (x0 + slant, band_bottom)]
            else:
                points = [(x0, band_mid), (x0 + slant, band_top), (x1 - slant, band_top),
                          (x1, band_mid), (x1 - slant, band_bottom), (x0 + slant, band_bottom)]

            # 隣り合う区間の斜め辺が同じ点で接するので、並べて描くと境目にX字のクロスができる
            poly = Polygon(points, closed=True, facecolor="#d9d9d9", edgecolor="black", linewidth=0.8, zorder=2)
            ax.add_patch(poly)
            ax.text((x0 + x1) / 2, band_mid, text, fontsize=8, ha="center", va="center", zorder=3)

    def methodDrawTimer(self, ax, timer, row_count):
        if timer["row"] >= len(self.varSignals):
            return  # 対象の行が削除されていたら、安全のため何も描かない

        top_y = row_count - timer["row"]
        band_bottom = top_y - 0.8
        band_top = top_y - 0.3
        width = timer["end_col"] - timer["start_col"]
        color = timer.get("color", "#ff6f61")  # 色機能が無かった頃のJSONにも対応

        rect = Rectangle((timer["start_col"], band_bottom), width, band_top - band_bottom,
                          facecolor=color, alpha=0.5, edgecolor="none", zorder=1)
        ax.add_patch(rect)
        ax.text((timer["start_col"] + timer["end_col"]) / 2, (band_bottom + band_top) / 2,
                timer["label"], fontsize=8, ha="center", va="center", zorder=2)

    # 矢印の始点/終点が実際に触れるべきy座標を、明示的なレベル("H"/"L"/None)から
    # 計算する。以前は前後のマスの状態から推測していたが、ON角/OFF角を別々に
    # 選べるようにしたため、レベルは呼び出し側(クリック時に選ばれたドット)から
    # そのまま受け取るだけでよくなった。
    def methodComputeArrowY(self, row_index, top_y, level):
        signal = self.varSignals[row_index]
        if signal["type"] != "digital" or level is None:
            return top_y - 0.55  # data行(またはレベル不明)は、今まで通り行の中央にする

        low_y = top_y - 0.75
        high_y = top_y - 0.35
        return high_y if level == "H" else low_y

    # 「最初は大きく膨らんで、終点に近づくとまっすぐ刺さる」曲線のパスを作る。
    # matplotlibの標準の"arc3"(始点から終点まで一定半径の円弧)だと対称な
    # ふくらみ方になってしまうので、3次ベジェ曲線を自前で組み立てている。
    #   ・制御点1(始点寄り): 進行方向と垂直な向きに大きくオフセットさせる
    #     → これが「最初の膨らみ」を作る
    #   ・制御点2(終点のすぐ手前): 終点にほぼ重なる位置に置く
    #     → これにより、曲線は終点直前でほぼ直線になり、まっすぐ刺さって見える
    def methodBuildEaseOutCurvePath(self, start_x, start_y, end_x, end_y, bulge_sign):
        dx = end_x - start_x
        dy = end_y - start_y
        distance = max((dx ** 2 + dy ** 2) ** 0.5, 0.001)  # 0除算を避けるための下限
        perp_x, perp_y = -dy / distance, dx / distance  # 進行方向に垂直な単位ベクトル
        bulge = 0.55 * bulge_sign  # 膨らみの大きさと向き(トリガ/条件で左右を変える)

        control1_x = start_x + dx * 0.25 + perp_x * bulge
        control1_y = start_y + dy * 0.25 + perp_y * bulge

        # 制御点2は「制御点1から終点へ向かう向き」に沿って終点の少し手前に置く。
        # 以前は始点→終点の直線方向(dx,dy)に沿って置いていたため、カーブの
        # 実際の流れ(膨らみ側から来る向き)と食い違い、先端の直前でカクッと
        # 折れてしまい、矢印の三角が歪んで見える原因になっていた。
        c1_to_end_x = end_x - control1_x
        c1_to_end_y = end_y - control1_y
        c1_to_end_len = max((c1_to_end_x ** 2 + c1_to_end_y ** 2) ** 0.5, 0.001)
        shrink = min(0.15, c1_to_end_len * 0.3)  # 終点手前に置く距離(近すぎ・遠すぎを防ぐ)
        control2_x = end_x - c1_to_end_x / c1_to_end_len * shrink
        control2_y = end_y - c1_to_end_y / c1_to_end_len * shrink

        vertices = [(start_x, start_y), (control1_x, control1_y), (control2_x, control2_y), (end_x, end_y)]
        codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4]
        return Path(vertices, codes)

    # トリガ/条件矢印を1本描く。
    # 横方向にしっかり動く矢印はまっすぐな直線、真上/真下に近い矢印は
    # 「最初膨らんで終点でまっすぐになる」曲線で描く(横一直線の流れを邪魔しないため)。
    def methodDrawArrow(self, ax, arrow, row_count):
        start_row, start_x, start_level = arrow["start"]
        end_row, end_x, end_level = arrow["end"]

        start_y = self.methodComputeArrowY(start_row, row_count - start_row, start_level)
        end_y = self.methodComputeArrowY(end_row, row_count - end_row, end_level)

        is_vertical = abs(start_x - end_x) < 0.05  # 横方向にほぼ動いていない

        # 色は種類で固定(選択式にはしていない)。古い保存データの"color"キーは無視する。
        if arrow["kind"] == "trigger":
            color, linewidth, linestyle, bulge_sign = "#7b2fbe", 1.6, "solid", -1
        else:
            color, linewidth, linestyle, bulge_sign = "#ff8c42", 1.3, "dashed", 1

        if is_vertical:
            # 独自のベジェ曲線パスをFancyArrowPatchに渡して描く
            path = self.methodBuildEaseOutCurvePath(start_x, start_y, end_x, end_y, bulge_sign)
            patch = FancyArrowPatch(path=path, arrowstyle="-|>", color=color,
                                     linewidth=linewidth, linestyle=linestyle, mutation_scale=12, zorder=5)
            ax.add_patch(patch)
            label_x, label_y = path.vertices[1]  # ラベルは膨らみの頂点付近に置く
            label_y += 0.12
        else:
            # 横方向にしっかり動く矢印はシンプルにまっすぐ描く
            style = dict(arrowstyle="-|>", color=color, linewidth=linewidth, linestyle=linestyle,
                         connectionstyle="arc3,rad=0")
            ax.annotate("", xy=(end_x, end_y), xytext=(start_x, start_y), arrowprops=style, zorder=5)
            label_x = (start_x + end_x) / 2
            label_y = (start_y + end_y) / 2 + 0.15

        if arrow["label"]:
            ax.text(label_x, label_y, arrow["label"], fontsize=7, color=color, ha="center", zorder=5)

    # Arrow Mode中に表示するドットを描く: 各行のスナップ可能な点(ON角/OFF角/
    # マス中間点)すべてに、小さいグレーの点を実際の波形の線の位置に重ねて表示する。
    # 選択中の始点だけは大きく赤いドットにする。
    def methodDrawArrowModeDots(self, ax, row_count):
        for row_index, signal in enumerate(self.varSignals):
            top_y = row_count - row_index
            for x, level in self.methodListSnapCandidates(row_index):
                y = self.methodComputeArrowY(row_index, top_y, level)
                if self.varArrowModeStartPoint == (row_index, x, level):
                    ax.plot(x, y, marker="o", markersize=9, color="#e74c3c", zorder=6)
                else:
                    ax.plot(x, y, marker="o", markersize=4, color="#999999", alpha=0.55, zorder=6)

    # チャート右上に、Trigger/Condition矢印の見本を常に表示する簡易凡例
    def methodDrawLegend(self, ax, row_count):
        legend_x = self.varTimeSteps + 0.6
        top = row_count + 0.55

        ax.annotate("", xy=(legend_x + 0.4, top - 0.05), xytext=(legend_x, top - 0.35),
                    arrowprops=dict(arrowstyle="-|>", color="#7b2fbe", linewidth=1.6, linestyle="solid"))
        ax.text(legend_x + 0.55, top - 0.2, "Trigger", fontsize=8, va="center")

        top2 = top - 0.55
        ax.annotate("", xy=(legend_x + 0.4, top2 - 0.05), xytext=(legend_x, top2 - 0.35),
                    arrowprops=dict(arrowstyle="-|>", color="#ff8c42", linewidth=1.3, linestyle="dashed"))
        ax.text(legend_x + 0.55, top2 - 0.2, "Condition", fontsize=8, va="center")

    # ============================================================
    # PNG出力(Excel/PowerPoint貼付用)
    # ============================================================
    def methodExportPng(self):
        if not self.varSignals:
            messagebox.showwarning("Export error", "There are no signals to export.")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
            title="Choose where to save the PNG"
        )
        if not save_path:
            return

        # 画面表示(低dpi)とは別に、印刷やExcel貼付に耐える高解像度(300dpi)で描き直す
        export_fig = Figure(figsize=(11, 0.9 * len(self.varSignals) + 1.5), dpi=300)
        export_ax = export_fig.add_subplot(111)
        self.methodDrawChart(export_ax)  # 画面と全く同じ描画関数を使うので見た目がズレない
        export_fig.savefig(save_path, bbox_inches="tight")
        messagebox.showinfo("Done", f"Saved PNG to:\n{save_path}\nYou can paste it directly into Excel or PowerPoint.")

    # ============================================================
    # 設定の保存/読込(JSON)
    # ============================================================
    def methodSaveJson(self):
        save_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON file", "*.json")],
            title="Choose where to save"
        )
        if not save_path:
            return

        data = {
            "varSignals": self.varSignals,
            "varCellStates": self.varCellStates,
            "varCellAnnotations": self.varCellAnnotations,
            "varArrows": self.varArrows,
            "varTimers": self.varTimers,
            "varMarkedColumns": list(self.varMarkedColumns),  # setはJSONにできないのでlistに変換
            "varNoteText": self.varNoteText,
            "varTimeSteps": self.varTimeSteps,
        }
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Done", "Saved.")

    def methodLoadJson(self):
        load_path = filedialog.askopenfilename(
            filetypes=[("JSON file", "*.json")],
            title="Choose a file to load"
        )
        if not load_path:
            return

        with open(load_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.methodPushUndoSnapshot()
        self.varSignals = data["varSignals"]
        self.varCellStates = data["varCellStates"]
        self.varTimeSteps = data["varTimeSteps"]
        # 矢印の(行,x)が2要素だった古い保存ファイルにも対応: レベル情報が無ければ
        # Noneで補い、行の真ん中に表示するフォールバックのまま扱う
        loaded_arrows = data["varArrows"]
        for arrow in loaded_arrows:
            if len(arrow["start"]) == 2:
                arrow["start"] = (arrow["start"][0], arrow["start"][1], None)
            if len(arrow["end"]) == 2:
                arrow["end"] = (arrow["end"][0], arrow["end"][1], None)
        self.varArrows = loaded_arrows
        # .get(キー, デフォルト値) にしているのは、その機能が無かった頃の
        # 古いJSONファイルを読み込んでもエラーにならないようにするため
        self.varCellAnnotations = data.get(
            "varCellAnnotations", [[""] * self.varTimeSteps for _ in self.varSignals]
        )
        self.varTimers = data.get("varTimers", [])
        self.varMarkedColumns = set(data.get("varMarkedColumns", []))
        self.varNoteText = data.get("varNoteText", "")
        self.varTimeStepsEntry.set(self.varTimeSteps)
        self.methodRedraw()


if __name__ == "__main__":
    root = tk.Tk()             # Tkinterのメインウィンドウを1つ作る
    app = TimingChartApp(root)  # このウィンドウの中身をTimingChartAppが全部作り込む
    root.mainloop()             # ユーザー操作を待ち続けるループを開始する
