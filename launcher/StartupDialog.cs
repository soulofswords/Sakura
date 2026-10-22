using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

// Native, lightweight launcher UI. No browser or AI runtime starts until a mode is chosen.
sealed class StartupDialog : Form {
 internal string SelectedMode;
 internal string ApiKey = "";
 readonly string project;
 readonly TextBox keyBox;
 readonly Label keyHint;
 readonly Panel keyFrame;
 readonly StartupProviderCombo apiProvider;
 readonly TextBox cloudModel;
 static readonly Color Background = Color.FromArgb(12,15,26);
 static readonly Color Muted = Color.FromArgb(145,155,180);
 static readonly Color Cyan = Color.FromArgb(97,225,235);

 internal StartupDialog(string project) {
  this.project=project;
  Text="Sakura Companion — Choose startup mode";
  Font=new Font("Segoe UI",10);
  AutoScaleDimensions=new SizeF(96,96); AutoScaleMode=AutoScaleMode.Dpi;
  ClientSize=new Size(620,755); BackColor=Background; ForeColor=Color.White;
  FormBorderStyle=FormBorderStyle.None; StartPosition=FormStartPosition.CenterScreen;
  MaximizeBox=false; MinimizeBox=false; DoubleBuffered=true;
  Icon=new Icon(Path.Combine(project,"launcher","companion.ico"));

  var close=new StartupCloseButton {Location=new Point(566,6),Size=new Size(42,34),
   BackColor=Background,ForeColor=Muted,
   AccessibleName="Close startup chooser",TabIndex=5,DialogResult=DialogResult.Cancel,Cursor=Cursors.Hand};
  close.Click+=(s,e)=>Close(); Controls.Add(close); CancelButton=close;
  Controls.Add(LabelAt("CHOOSE YOUR EXPERIENCE",32,59,500,23,9,Cyan,FontStyle.Bold));
  Controls.Add(LabelAt("Welcome to Sakura",30,86,555,48,28,Color.FromArgb(242,245,255),FontStyle.Bold));
  Controls.Add(LabelAt("One companion. Three ways to connect.",33,137,550,26,11,Muted,FontStyle.Regular));
  Controls.Add(LabelAt("CLOUD API KEY",33,183,230,22,9,Muted,FontStyle.Bold));
  var providerFrame=new StartupInputFrame {Location=new Point(320,174),Size=new Size(268,34)};
  apiProvider=new StartupProviderCombo {Location=new Point(10,4),Size=new Size(248,26),
   BackColor=providerFrame.BackColor,ForeColor=Color.White,AccessibleName="API provider"};
  apiProvider.Items.AddRange(new object[]{"Auto-detect key","Google Gemini","OpenAI","Anthropic Claude","DeepSeek","OpenRouter","Groq","xAI"});apiProvider.SelectedIndex=0;
  providerFrame.Controls.Add(apiProvider);Controls.Add(providerFrame);

  keyFrame=new StartupInputFrame {Location=new Point(32,210),Size=new Size(556,42)};
  keyBox=new TextBox {Location=new Point(14,11),Size=new Size(528,24),BorderStyle=BorderStyle.None,
   BackColor=keyFrame.BackColor,ForeColor=Color.FromArgb(230,236,250),UseSystemPasswordChar=true,
   AccessibleName="Cloud API key. Leave blank to use your saved provider and key.",TabIndex=0};
  keyBox.Enter+=(s,e)=>keyFrame.Invalidate(); keyBox.Leave+=(s,e)=>keyFrame.Invalidate();
  keyFrame.Controls.Add(keyBox); Controls.Add(keyFrame);
  keyHint=LabelAt("Blank keeps saved key. Model ID (optional):",33,258,350,28,8,Muted,FontStyle.Regular);
  Controls.Add(keyHint);
  var modelFrame=new StartupInputFrame {Location=new Point(393,255),Size=new Size(195,30)};
  cloudModel=new TextBox {Location=new Point(10,5),Size=new Size(175,22),BackColor=modelFrame.BackColor,ForeColor=Color.White,BorderStyle=BorderStyle.None,AccessibleName="Cloud model ID"};
  modelFrame.Controls.Add(cloudModel);Controls.Add(modelFrame);

  string[] modes={"gemini","local","vtuber"};
  string[] titles={"Cloud API","Local LLM","VTuber"};
  string[] descriptions={"Cloud AI companion · Use your API key","On-device AI companion · Run on this PC","Face + hand tracking · No AI models loaded"};
  string[] tags={"CLOUD","LOCAL","TRACKING"};
  Color[] accents={Cyan,Color.FromArgb(180,153,255),Color.FromArgb(245,144,196)};
  ModeCard firstModeCard=null;
  for(int i=0;i<modes.Length;i++) {
   string mode=modes[i];
   var card=new ModeCard(titles[i],descriptions[i],tags[i],accents[i],i) {
    Location=new Point(32,295+i*80),Size=new Size(556,76),TabIndex=i+1};
   card.Click+=(s,e)=>SelectMode(mode); Controls.Add(card);
   if(i==0)firstModeCard=card;
  }
  Controls.Add(LabelAt("This app is currently under development.\nYour feedback is most important.",33,625,550,44,10,Color.FromArgb(205,213,232),FontStyle.Regular));
  var discord=new LinkLabel {Text="Join my Discord and DM me",Location=new Point(33,675),Size=new Size(550,24),
   Font=new Font("Segoe UI",9,FontStyle.Bold),LinkColor=Cyan,ActiveLinkColor=Color.FromArgb(180,153,255),
   VisitedLinkColor=Cyan,BackColor=Color.Transparent,TabStop=true,AccessibleName="Join the Sakura Discord and send feedback"};
  discord.Links.Add(0,discord.Text.Length,"https://discord.gg/kgxeMRFWDw");
  discord.LinkClicked+=(s,e)=>Process.Start(new ProcessStartInfo((string)e.Link.LinkData){UseShellExecute=true});
  Controls.Add(discord);
  Controls.Add(LabelAt("You can change your AI provider later in Settings.",33,714,550,22,9,Muted,FontStyle.Regular));
  Shown+=(s,e)=>{BringToFront();Activate();ActiveControl=firstModeCard;};
 }
 void SelectMode(string mode) {
  if(mode=="local" && !LocalModelDialog.Installed(project)) {
   if(MessageBox.Show(this,"Are you sure you want to run Local LLM? This downloads an optional runtime and Qwen model to Sakura's folder.","Set up local AI",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes)return;
   using(var setup=new LocalModelDialog(project))if(setup.ShowDialog(this)!=DialogResult.OK)return;
  }
  if(mode=="gemini" && keyBox.Text.Trim().Length==0 && !File.Exists(Path.Combine(project,".gemini-key.bin")) && !File.Exists(Path.Combine(project,".cloud-keys.bin"))) {
   keyHint.Text="Enter an API key to continue."; keyHint.ForeColor=Color.FromArgb(255,151,177);
   keyBox.Focus(); return;
  }
  if(mode=="gemini" && keyBox.Text.Trim().Length>0) {
   string key=keyBox.Text.Trim();string[] providers={"auto","gemini","openai","anthropic","deepseek","openrouter","groq","xai"};string provider=providers[apiProvider.SelectedIndex];
   if(provider=="auto") {
    if(key.StartsWith("AIza"))provider="gemini";else if(key.StartsWith("sk-ant-"))provider="anthropic";else if(key.StartsWith("sk-or-"))provider="openrouter";else if(key.StartsWith("sk-proj-")||key.StartsWith("sk-svcacct-"))provider="openai";else if(key.StartsWith("gsk_"))provider="groq";else if(key.StartsWith("xai-"))provider="xai";
    else {keyHint.Text="Ambiguous key. Select its provider above.";keyHint.ForeColor=Color.FromArgb(255,151,177);return;}
   }
   if((provider=="groq"||provider=="xai"||provider=="openrouter")&&cloudModel.Text.Trim().Length==0){keyHint.Text="Enter this provider's model ID on the right.";return;}
   Environment.SetEnvironmentVariable("SAKURA_START_API_PROVIDER",provider);
   Environment.SetEnvironmentVariable("SAKURA_START_CLOUD_MODEL",cloudModel.Text.Trim());
  }
  SelectedMode=mode; ApiKey=mode=="gemini"?keyBox.Text.Trim():""; DialogResult=DialogResult.OK; Close();
 }
 static Label LabelAt(string text,int x,int y,int width,int height,float size,Color color,FontStyle style) {
  return new Label {Text=text,Location=new Point(x,y),Size=new Size(width,height),ForeColor=color,
   BackColor=Color.Transparent,Font=new Font("Segoe UI",size,style)};
 }
 internal static GraphicsPath Round(RectangleF r,float radius) {
  var path=new GraphicsPath(); float d=radius*2;
  path.AddArc(r.X,r.Y,d,d,180,90); path.AddArc(r.Right-d,r.Y,d,d,270,90);
  path.AddArc(r.Right-d,r.Bottom-d,d,d,0,90); path.AddArc(r.X,r.Bottom-d,d,d,90,90); path.CloseFigure(); return path;
 }
 protected override void OnPaint(PaintEventArgs e) {
  base.OnPaint(e); var g=e.Graphics; g.SmoothingMode=SmoothingMode.AntiAlias;
  float scale=ClientSize.Width/620f;
  var state=g.Save();g.ScaleTransform(scale,scale);
  using(var path=Round(new RectangleF(.5f,.5f,619,ClientSize.Height/scale-1),16))
  using(var pen=new Pen(Color.FromArgb(53,63,88)))g.DrawPath(pen,path);
  using(var line=new LinearGradientBrush(new Rectangle(32,46,556,2),Cyan,Color.FromArgb(168,113,244),0f))g.FillRectangle(line,32,46,556,2);
  g.DrawIcon(Icon,new Rectangle(32,14,22,22));
  g.Restore(state);
  using(var font=new Font("Segoe UI",9,FontStyle.Bold))TextRenderer.DrawText(g,"SAKURA  /  COMPANION",font,new Point((int)(65*scale),(int)(17*scale)),Muted);
 }
 protected override void OnResize(EventArgs e) {
  base.OnResize(e);
  if(Width>32 && Height>32) {using(var path=Round(new RectangleF(0,0,Width,Height),16)) {var old=Region;Region=new Region(path);if(old!=null)old.Dispose();}}
 }
 protected override void WndProc(ref Message message) {
  base.WndProc(ref message);
  // Drag the custom header, while buttons/text boxes keep normal hit testing.
  if(message.Msg==0x84 && message.Result==(IntPtr)1) {
   var point=PointToClient(new Point(unchecked((short)(long)message.LParam),unchecked((short)((long)message.LParam>>16))));
   float scale=ClientSize.Width/620f;
   if(point.Y<46*scale && point.X<Width-60*scale)message.Result=(IntPtr)2;
  }
 }
}

sealed class StartupProviderCombo : Button {
 internal readonly System.Collections.Generic.List<object> Items=new System.Collections.Generic.List<object>();
 readonly ContextMenuStrip providerMenu;
 int selectedIndex;
 internal int SelectedIndex {get{return selectedIndex;}set{selectedIndex=value;Text=Items.Count>value?Items[value].ToString():"";Invalidate();}}
 internal StartupProviderCombo() {
  FlatStyle=FlatStyle.Flat;FlatAppearance.BorderSize=0;Cursor=Cursors.Hand;
  SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer,true);
  providerMenu=new ContextMenuStrip {ShowImageMargin=false,Renderer=new StartupProviderMenuRenderer()};
 }
 protected override void OnPaint(PaintEventArgs e) {
  var g=e.Graphics;g.Clear(BackColor);g.SmoothingMode=SmoothingMode.AntiAlias;
  TextRenderer.DrawText(g,Text,Font,new Rectangle(3,0,Math.Max(0,Width-27),Height),ForeColor,
   TextFormatFlags.Left|TextFormatFlags.VerticalCenter|TextFormatFlags.EndEllipsis|TextFormatFlags.NoPrefix);
  float x=Width-11,y=Height/2f;
  using(var pen=new Pen(Color.FromArgb(145,155,180),1.6f)) {
   g.DrawLine(pen,x-4,y-2,x,y+2);g.DrawLine(pen,x,y+2,x+4,y-2);
  }
 }
 protected override void OnClick(EventArgs e) {
  base.OnClick(e);
  if(IsDisposed||Disposing)return;
  if(providerMenu.Visible){providerMenu.Close();return;}
  providerMenu.BackColor=BackColor;providerMenu.ForeColor=ForeColor;providerMenu.Font=Font;
  if(providerMenu.Items.Count==0)for(int i=0;i<Items.Count;i++) {
   int index=i;var item=new ToolStripMenuItem(Items[i].ToString());
   item.Click+=(s,a)=>{SelectedIndex=index;};providerMenu.Items.Add(item);
  }
  for(int i=0;i<providerMenu.Items.Count;i++)((ToolStripMenuItem)providerMenu.Items[i]).Checked=i==selectedIndex;
  // Reuse the popup. Disposing in Closed interrupts native click/close handling.
  providerMenu.Show(this,new Point(0,Height));
 }
 protected override void Dispose(bool disposing) {
  if(disposing)providerMenu.Dispose();
  base.Dispose(disposing);
 }
 protected override void OnKeyDown(KeyEventArgs e) {
  if(e.KeyCode==Keys.Down && !e.Alt){SelectedIndex=Math.Min(Items.Count-1,selectedIndex+1);e.Handled=true;}
  else if(e.KeyCode==Keys.Up){SelectedIndex=Math.Max(0,selectedIndex-1);e.Handled=true;}
  else if(e.KeyCode==Keys.F4 || (e.Alt&&e.KeyCode==Keys.Down)){OnClick(EventArgs.Empty);e.Handled=true;}
  base.OnKeyDown(e);
 }
}
sealed class StartupProviderMenuRenderer : ToolStripProfessionalRenderer {
 protected override void OnRenderToolStripBackground(ToolStripRenderEventArgs e){e.Graphics.Clear(Color.FromArgb(21,27,44));}
 protected override void OnRenderMenuItemBackground(ToolStripItemRenderEventArgs e){
  using(var fill=new SolidBrush(e.Item.Selected?Color.FromArgb(39,57,76):Color.FromArgb(21,27,44)))e.Graphics.FillRectangle(fill,new Rectangle(Point.Empty,e.Item.Size));
 }
 protected override void OnRenderItemText(ToolStripItemTextRenderEventArgs e){e.TextColor=Color.FromArgb(230,236,250);base.OnRenderItemText(e);}
}

sealed class StartupInputFrame : Panel {
 internal StartupInputFrame() {
  BackColor=Color.FromArgb(21,27,44);
  SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer|ControlStyles.ResizeRedraw,true);
 }
 protected override void OnControlAdded(ControlEventArgs e) {
  base.OnControlAdded(e);
  e.Control.Enter+=(s,a)=>Invalidate();e.Control.Leave+=(s,a)=>Invalidate();
 }
 protected override void OnPaintBackground(PaintEventArgs e) {
  e.Graphics.Clear(Parent==null?Color.FromArgb(12,15,26):Parent.BackColor);
 }
 protected override void OnPaint(PaintEventArgs e) {
  var g=e.Graphics;g.SmoothingMode=SmoothingMode.AntiAlias;
  using(var path=StartupDialog.Round(new RectangleF(.75f,.75f,Width-1.5f,Height-1.5f),10))
  using(var fill=new SolidBrush(BackColor))
  using(var border=new Pen(ContainsFocus?Color.FromArgb(97,225,235):Color.FromArgb(48,59,82),ContainsFocus?1.5f:1)) {
   g.FillPath(fill,path);g.DrawPath(border,path);
  }
 }
}

sealed class StartupCloseButton : Button {
 bool hovered;
 internal StartupCloseButton() {
  FlatStyle=FlatStyle.Flat;FlatAppearance.BorderSize=0;
  SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer,true);
 }
 protected override void OnMouseEnter(EventArgs e){hovered=true;Invalidate();base.OnMouseEnter(e);}
 protected override void OnMouseLeave(EventArgs e){hovered=false;Invalidate();base.OnMouseLeave(e);}
 protected override void OnPaint(PaintEventArgs e) {
  var g=e.Graphics;g.Clear(hovered?Color.FromArgb(48,28,44):BackColor);
  g.SmoothingMode=SmoothingMode.AntiAlias;
  float x=Width/2f,y=Height/2f,r=Math.Min(Width,Height)*.14f;
  using(var pen=new Pen(ForeColor,Math.Max(1.5f,Height/22f))) {
   g.DrawLine(pen,x-r,y-r,x+r,y+r);g.DrawLine(pen,x-r,y+r,x+r,y-r);
  }
  if(Focused)ControlPaint.DrawFocusRectangle(g,Rectangle.Inflate(ClientRectangle,-3,-3));
 }
}

sealed class ModeCard : Button {
 readonly string title,description,tag;
 readonly Color accent;
 readonly int symbol;
 bool hovered;
 internal ModeCard(string title,string description,string tag,Color accent,int symbol) {
  this.title=title;this.description=description;this.tag=tag;this.accent=accent;this.symbol=symbol;
  Text=title; AccessibleName=title+". "+description; Cursor=Cursors.Hand;
  FlatStyle=FlatStyle.Flat; FlatAppearance.BorderSize=0; BackColor=Color.FromArgb(12,15,26);
  SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer,true);
 }
 protected override void OnMouseEnter(EventArgs e){hovered=true;Invalidate();base.OnMouseEnter(e);}
 protected override void OnMouseLeave(EventArgs e){hovered=false;Invalidate();base.OnMouseLeave(e);}
 protected override void OnGotFocus(EventArgs e){base.OnGotFocus(e);Invalidate();}
 protected override void OnLostFocus(EventArgs e){base.OnLostFocus(e);Invalidate();}
 protected override void OnPaint(PaintEventArgs e) {
  var g=e.Graphics;g.Clear(BackColor);g.SmoothingMode=SmoothingMode.AntiAlias;
  using(var path=StartupDialog.Round(new RectangleF(1,1,Width-3,Height-3),12))
  using(var fill=new LinearGradientBrush(ClientRectangle,Color.FromArgb(hovered?34:23,hovered?43:30,hovered?63:46),Color.FromArgb(18,23,37),0f))
  using(var pen=new Pen(hovered||Focused?accent:Color.FromArgb(44,54,76),Focused?2:1)) {g.FillPath(fill,path);g.DrawPath(pen,path);}
  float scale=Height/82f, logicalWidth=Width/scale;
  var state=g.Save();g.ScaleTransform(scale,scale);
  using(var brush=new SolidBrush(Color.FromArgb(30,accent)))g.FillEllipse(brush,18,19,44,44);
  using(var pen=new Pen(accent,2)) {
   if(symbol==0){g.DrawLine(pen,40,29,40,53);g.DrawLine(pen,28,41,52,41);g.DrawLine(pen,32,33,48,49);g.DrawLine(pen,48,33,32,49);}
   else if(symbol==1){g.DrawRectangle(pen,30,31,20,20);for(int i=0;i<3;i++){int n=33+i*7;g.DrawLine(pen,n,26,n,30);g.DrawLine(pen,n,52,n,56);g.DrawLine(pen,25,n,29,n);g.DrawLine(pen,51,n,55,n);}}
   else if(symbol==2){g.DrawEllipse(pen,29,29,22,24);g.DrawLine(pen,34,58,46,58);g.DrawLine(pen,36,37,36,39);g.DrawLine(pen,44,37,44,39);g.DrawArc(pen,35,40,10,7,0,180);}
   else {g.DrawArc(pen,29,29,22,24,0,360);g.DrawLine(pen,34,58,46,58);g.DrawLine(pen,36,37,36,39);g.DrawLine(pen,44,37,44,39);g.DrawArc(pen,35,40,10,7,0,180);}
   g.DrawLine(pen,logicalWidth-30,35,logicalWidth-24,41);g.DrawLine(pen,logicalWidth-24,41,logicalWidth-30,47);
  }
  g.Restore(state);
  using(var heading=new Font("Segoe UI",14,FontStyle.Bold))
  using(var body=new Font("Segoe UI",9))
  using(var badge=new Font("Segoe UI",8,FontStyle.Bold)) {
   TextRenderer.DrawText(g,title,heading,Scaled(78,16,220,27,scale),Color.FromArgb(240,244,255),TextFormatFlags.Left|TextFormatFlags.NoPadding);
   TextRenderer.DrawText(g,description,body,Scaled(79,47,logicalWidth-120,23,scale),Color.FromArgb(154,166,189),TextFormatFlags.Left|TextFormatFlags.NoPadding);
   TextRenderer.DrawText(g,tag,badge,Scaled(logicalWidth-137,22,91,22,scale),accent,TextFormatFlags.Right|TextFormatFlags.NoPadding);
  }
 }
 static Rectangle Scaled(float x,float y,float width,float height,float scale) {
  return new Rectangle((int)(x*scale),(int)(y*scale),(int)(width*scale),(int)(height*scale));
 }
}
