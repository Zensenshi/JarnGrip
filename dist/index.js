// SPDX-License-Identifier: GPL-3.0-only
const manifest={name:"JarnGrip"};
const init=window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if(!init)throw new Error("Decky Loader API unavailable");
let api;try{api=init.connect(2,manifest.name)}catch{api=init.connect(1,manifest.name)}
const call=api.call, jsx=SP_JSX.jsx, jsxs=SP_JSX.jsxs;
// Each game's control ids and their default Linux key codes, and the controls that send a modifier with their key by
// default, as in driver/bin/pad_model.py.
const wowDefaults={character:46,spellbook:25,talents:49,quest_log:38,map:50,social:24,guild:36,group_finder:23,achievements:21,professions:37,bags:48,system:1,self:59,party_1:60,party_2:61,party_3:62,party_4:63,next_enemy:15,previous_enemy:15,sheathe_weapons:44,sit_stand:45,chat_page_up:104,chat_page_down:109,screenshot:99,slot_1:2,slot_2:3,slot_3:4,slot_4:5,slot_5:6,slot_6:7,slot_7:8,slot_8:9,slot_9:10,slot_10:11,slot_11:12,slot_12:13};
const wowMods={previous_enemy:["shift"]};
const ffxiDefaults={main_menu:12,confirm:28,cancel:1,equipment:18,items:23,magic:50,job_abilities:36,weapon_skills:17,pet_commands:48,self:59,party_1:60,party_2:61,party_3:62,party_4:63,party_5:64,nearest_npc:66,nearest_player:67,lock_target:55,attack:30,check:46,ranged_attack:32,macro_set_up:103,macro_set_down:108,reply_to_tell:19,party_chat:25,linkshell_chat:38,say:31,slot_1:2,slot_2:3,slot_3:4,slot_4:5,slot_5:6,slot_6:7,slot_7:8,slot_8:9,slot_9:10,slot_10:11,slot_11:12,slot_12:13};
const ffxiMods={equipment:["ctrl"],items:["ctrl"],magic:["ctrl"],job_abilities:["ctrl"],weapon_skills:["ctrl"],pet_commands:["ctrl"],attack:["ctrl"],check:["ctrl"],ranged_attack:["ctrl"],macro_set_up:["ctrl"],macro_set_down:["ctrl"],reply_to_tell:["ctrl"],party_chat:["ctrl"],linkshell_chat:["ctrl"],say:["ctrl"]};
const desktopDefaults={undo:44,redo:44,cut:45,copy:46,paste:47,select_all:30,find:33,save:31,esc:1,delete:111,tab:15,enter:28,home:102,end:107,page_up:104,page_down:109,back:105,forward:106,reload:63,address_bar:38,new_tab:20,close_tab:17,previous_tab:15,next_tab:15,reopen_tab:20,bookmark:32,zoom_out:12,zoom_in:13,switch_window:15,close_window:62,full_screen:87,volume_up:115,mute:113,volume_down:114,previous:165,play_pause:164,next:163,screenshot:99,menu:127};
const desktopMods={undo:["ctrl"],redo:["ctrl","shift"],cut:["ctrl"],copy:["ctrl"],paste:["ctrl"],select_all:["ctrl"],find:["ctrl"],save:["ctrl"],back:["alt"],forward:["alt"],address_bar:["ctrl"],new_tab:["ctrl"],close_tab:["ctrl"],previous_tab:["ctrl","shift"],next_tab:["ctrl"],reopen_tab:["ctrl","shift"],bookmark:["ctrl"],zoom_out:["ctrl"],zoom_in:["ctrl"],switch_window:["alt"],close_window:["alt"]};
// swipes: what a swipe up and down on a number adds.
const GAMES={wow:{name:"World of Warcraft",short:"WoW",defaults:wowDefaults,mods:wowMods,swipes:["Shift","Ctrl"]},
 ffxi:{name:"Final Fantasy XI",short:"FFXI",defaults:ffxiDefaults,mods:ffxiMods,swipes:["Ctrl","Alt"]},
 desktop:{name:"Desktop",short:"Desktop",defaults:desktopDefaults,mods:desktopMods,swipes:["Ctrl","Alt"]}};
const gameOptions=Object.entries(GAMES).map(([id,g])=>({data:id,label:g.name}));
const gameOf=cfg=>GAMES[cfg.game]||GAMES.wow;
// The number block's slots by the key they are on the pad ("number =" for slot_12).
const controlName=x=>{const n=/^slot_(\d+)$/.exec(x);return n?`number ${["1","2","3","4","5","6","7","8","9","0","-","="][n[1]-1]}`:x.replaceAll("_"," ")};
const controlOptionsOf=cfg=>Object.keys(gameOf(cfg).defaults).map(x=>({data:x,label:controlName(x)}));
// The control to show: the one picked, if the game has it, or the game's first.
const controlIn=(cfg,control)=>control in gameOf(cfg).defaults?control:Object.keys(gameOf(cfg).defaults)[0];
// The key picker: [Linux key code, name].
const keyNames=[[30,"A"],[48,"B"],[46,"C"],[32,"D"],[18,"E"],[33,"F"],[34,"G"],[35,"H"],[23,"I"],[36,"J"],[37,"K"],[38,"L"],[50,"M"],[49,"N"],[24,"O"],[25,"P"],[16,"Q"],[19,"R"],[31,"S"],[20,"T"],[22,"U"],[47,"V"],[17,"W"],[45,"X"],[21,"Y"],[44,"Z"],[11,"0"],[2,"1"],[3,"2"],[4,"3"],[5,"4"],[6,"5"],[7,"6"],[8,"7"],[9,"8"],[10,"9"],[59,"F1"],[60,"F2"],[61,"F3"],[62,"F4"],[63,"F5"],[64,"F6"],[65,"F7"],[66,"F8"],[67,"F9"],[68,"F10"],[87,"F11"],[88,"F12"],[1,"Esc"],[15,"Tab"],[57,"Space"],[28,"Enter"],[14,"Backspace"],[58,"Caps Lock"],[103,"Up"],[108,"Down"],[105,"Left"],[106,"Right"],[127,"Menu"],[125,"Super"],[110,"Insert"],[111,"Delete"],[102,"Home"],[107,"End"],[104,"Page Up"],[109,"Page Down"],[12,"-"],[13,"="],[26,"["],[27,"]"],[39,";"],[40,"'"],[41,"`"],[43,"\\"],[51,","],[52,"."],[53,"/"],[82,"Numpad 0"],[79,"Numpad 1"],[80,"Numpad 2"],[81,"Numpad 3"],[75,"Numpad 4"],[76,"Numpad 5"],[77,"Numpad 6"],[71,"Numpad 7"],[72,"Numpad 8"],[73,"Numpad 9"],[98,"Numpad /"],[55,"Numpad *"],[74,"Numpad -"],[78,"Numpad +"],[83,"Numpad ."],[96,"Numpad Enter"],[69,"Num Lock"],[99,"Print Screen"],[70,"Scroll Lock"],[119,"Pause"],[164,"Play/Pause"],[165,"Previous Track"],[163,"Next Track"],[113,"Mute"],[114,"Volume Down"],[115,"Volume Up"],[42,"Left Shift"],[29,"Left Ctrl"],[56,"Left Alt"],[54,"Right Shift"],[97,"Right Ctrl"],[100,"Right Alt"]];
const keyLabel=Object.fromEntries(keyNames);
const MODS=["ctrl","shift","alt"];
const sortMods=mods=>MODS.filter(m=>mods.includes(m));
// What a control sends, as {key, mods}: the binding saved for it (a number keeps the default modifiers, text such as
// "shift+15" is the whole combination), or its default. The same rules as combo_for in driver/bin/pad_model.py.
const comboOf=(cfg,control)=>{const v=(cfg.bindings||{})[control],g=gameOf(cfg),mods=g.mods[control]||[];
 if(typeof v==="number"&&v>0&&v<248)return {key:v,mods};
 if(typeof v==="string"){const parts=v.toLowerCase().split("+").map(x=>x.trim()),key=Number(parts.pop());if(key>0&&key<248&&parts.every(p=>MODS.includes(p)))return {key,mods:sortMods(parts)}}
 return {key:g.defaults[control],mods}};
const comboText=c=>[...sortMods(c.mods).map(m=>m[0].toUpperCase()+m.slice(1)),keyLabel[c.key]||`key code ${c.key}`].join(" + ");
// The number pad's icons, as ICON_ID in main.py has them: a number's id for its tap, the id and the swipe for a swipe.
const numberOptions=["1","2","3","4","5","6","7","8","9","0","-","="].map((label,i)=>({data:`slot_${i+1}`,label}));
// The panel's own copy of the icons may be older than what the icon page saved: it never sends them back.
const saveConfig=c=>{const {icons,...rest}=c;return call("save_config",rest)};
// Theme ids as in driver/bin/pad_model.py.
const themeOptions=[{data:"classic",label:"Classic (stone and gold)"},{data:"charcoal",label:"Charcoal (slate and blue)"},{data:"dark",label:"Dark (pure black)"},{data:"glass",label:"Game Glass (your picture)"}];
// The shortcut opens or closes the pad from anywhere in Game Mode, a game included. Steam reports every controller's
// buttons to Decky's frontend whether or not this panel is open, as two bitmasks: ulButtons and ulUpperButtons. The
// shortcut is a pair of masks, [buttons, upper], all of which must be down; Home + Start by default, or whatever
// "Change" records (the AYN button, if Steam reports it).
const DEFAULT_SHORTCUT=[1<<13|1<<14,0];
// Touch sensing (touchpads, thumbsticks) is not a press, so it never becomes part of a recorded shortcut.
const TOUCH=[0xf<<17,3<<14];
const BUTTON_NAMES=[{0:"R2",1:"L2",2:"R1",3:"L1",4:"Y",5:"B",6:"X",7:"A",8:"Up",9:"Right",10:"Left",11:"Down",12:"Select",13:"Home",14:"Start",15:"L5",16:"R5",22:"L3",26:"R3"},{9:"L4",10:"R4",18:"Quick Access"}];
const shortcutText=masks=>masks.flatMap((m,i)=>[...Array(32).keys()].filter(b=>(m>>>b)&1).map(b=>BUTTON_NAMES[i][b]||`button ${i?"U":""}${b}`)).join(" + ");
const validShortcut=v=>Array.isArray(v)&&v.length===2&&v.every(Number.isInteger)&&(v[0]||v[1])?v.map(m=>m>>>0):DEFAULT_SHORTCUT;
// The AYN button below the screen, while its switch is on. With InputPlumber emulating a Steam Deck controller and the
// screenshot left on, it arrives here as Home + R1, Steam's screenshot chord, so that chord toggles the pad too. Any
// other way, it arrives as a key Steam does not report, which the backend's listener hears instead: a press only ever
// comes one of the two ways. With "Stop the screenshot" on it is always that key, so the chord is left to Steam.
const AYN_CHORD=[1<<13|1<<2,0];
let shortcutOn=true,shortcut=DEFAULT_SHORTCUT,aynChord=false,toggling=false,recording=null;
const setAyn=c=>{aynChord=!!c.ayn_button&&!c.ayn_no_screenshot};
const comboDown=new Map();  // controller index -> whether the shortcut was held at its last report
const latest=new Map();     // controller index -> its buttons at its last report
const homeButtons=on=>{try{DFL.Router?.[on?"EnableHomeAndQuickAccessButtons":"DisableHomeAndQuickAccessButtons"]?.()}catch{}};
const toggleFromShortcut=async()=>{
 toggling=true;
 homeButtons(false);  // a Home or Quick Access press in the shortcut must not also open Steam's menus
 setTimeout(()=>homeButtons(true),1000);
 try{
  const r=await call("set_enabled",!(await call("get_status")).enabled);
  api.toaster?.toast({title:"JarnGrip",body:r.error||(r.enabled?"Pad on":"Pad off")});
 }catch(e){console.error("[jarngrip] shortcut",e)}
 finally{toggling=false}
};
// Record the next press as the shortcut: wait for every button to be up (the A press on "Change" is still down), then
// collect every button pressed until all are up again. Resolves with [buttons, upper], or null after 10 s of nothing.
const recordShortcut=()=>new Promise(resolve=>{
 const done=masks=>{clearTimeout(recording.timer);recording=null;resolve(masks)};
 recording={armed:[...latest.values()].every(m=>!m[0]&&!m[1]),masks:[0,0],done,timer:setTimeout(()=>done(null),10000)};
});
const onControllerState=changes=>{
 for(const c of changes||[]){
  const now=[(c.ulButtons&~TOUCH[0])>>>0,(c.ulUpperButtons&~TOUCH[1])>>>0];
  latest.set(c.unControllerIndex,now);
  if(recording){
   if(!recording.armed){recording.armed=!now[0]&&!now[1];continue}
   recording.masks=recording.masks.map((m,i)=>(m|now[i])>>>0);
   if(!now[0]&&!now[1]&&(recording.masks[0]||recording.masks[1]))recording.done(recording.masks);
   continue;
  }
  const held=masks=>now.every((m,i)=>((m&masks[i])>>>0)===masks[i]);
  const down=(shortcutOn&&held(shortcut))||(aynChord&&held(AYN_CHORD));
  if(down&&!comboDown.get(c.unControllerIndex)&&!toggling)toggleFromShortcut();
  comboDown.set(c.unControllerIndex,down);
 }
};
// A category of the panel that opens and closes with a tap on its header, which says what is set inside while it is
// closed. Which are open is kept across openings of the menu and restarts. Steam may report one tap as both a click
// and an activation: the second within a moment is ignored.
const OPEN_KEY="jarngrip.openSections";
let openSections=(()=>{try{const v=JSON.parse(localStorage.getItem(OPEN_KEY)||"[]");return Array.isArray(v)?v:[]}catch{return []}})();
let lastFlip=0;
const chevron=open=>jsx("svg",{xmlns:"http://www.w3.org/2000/svg",viewBox:"0 0 24 24",width:20,height:20,fill:"none",stroke:"currentColor",strokeWidth:2.5,style:{transform:open?"rotate(90deg)":"none",transition:"transform .15s",opacity:.8},children:jsx("path",{d:"m9 6 6 6-6 6"})});
function Section({id,title,summary,children}){
 const [open,setOpen]=SP_REACT.useState(openSections.includes(id));
 const flip=()=>{const now=Date.now();if(now-lastFlip<350)return;lastFlip=now;const next=!open;
  openSections=next?[...openSections.filter(x=>x!==id),id]:openSections.filter(x=>x!==id);
  try{localStorage.setItem(OPEN_KEY,JSON.stringify(openSections))}catch{}setOpen(next)};
 return jsxs(DFL.PanelSection,{children:[
  jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:jsx("span",{style:{fontWeight:"bold",textTransform:"uppercase",letterSpacing:".04em",fontSize:13},children:title}),description:open?undefined:summary,focusable:true,highlightOnFocus:true,onActivate:flip,onClick:flip,childrenContainerWidth:"min",children:chevron(open)})},"header"),
  ...(open?children:[])]});
}
// What Remap a control is editing: the control picked, and a key or modifiers changed but not saved yet (combo, for
// that control; null shows what it sends now). Kept out of Content because Steam closes the Quick Access menu while a
// dropdown's list is open and reopens it after, and each reopening mounts Content afresh: picked inside it, the
// control went back to the first. The handlers of the Content that opened the list may run after it is gone, so
// the one mounted now hears of each change (listeners).
const remap={control:"character",combo:null,listeners:new Set()};
const setRemap=patch=>{Object.assign(remap,patch);remap.listeners.forEach(f=>f())};
// What the number keys show (the config's number_pad, as main.py keeps it). FFXI has no addon to name its keys, so
// names there are its numbers, and the panel says so.
const PAD_MODES=["numbers","names","icons"];
const padMode=cfg=>{const m=PAD_MODES.includes(cfg.number_pad)?cfg.number_pad:cfg.number_icons?"icons":"names";return m==="names"&&cfg.game!=="wow"?"numbers":m};
const padModeOptions=cfg=>[{data:"numbers",label:"Numbers"},...(cfg.game==="wow"?[{data:"names",label:"Spell names"}]:[]),{data:"icons",label:"Icons"}];
const padModeLabel=cfg=>({numbers:"Numbers",names:"Spell names",icons:"Icons"})[padMode(cfg)];
function Content(){
 const [status,setStatus]=SP_REACT.useState({enabled:false});
 const [cfg,setCfg]=SP_REACT.useState({game:"wow",bindings:{},profiles:{},active_profile:"Default",sensitivity:1,theme:"classic",haptics:true,haptics_strength:1,burn_in:true,clock_24h:false,desktop_mode:false});
 const [profile,setProfile]=SP_REACT.useState("Default");
 const [newProfile,setNewProfile]=SP_REACT.useState("");
 const [message,setMessage]=SP_REACT.useState("");
 const [pictures,setPictures]=SP_REACT.useState({folder:"~/Pictures/JarnGrip",pictures:[]});
 const [,redraw]=SP_REACT.useReducer(n=>n+1,0);
 SP_REACT.useEffect(()=>{remap.listeners.add(redraw);return()=>{remap.listeners.delete(redraw)}},[]);
 const control=controlIn(cfg,remap.control);
 const combo=remap.combo&&remap.combo.control===control?remap.combo.value:comboOf(cfg,control);
 const setCombo=value=>setRemap({combo:{control,value}});
 const refresh=async()=>{try{const s=await call("get_status"),c=await call("get_config");setStatus(s);setCfg(c);setProfile(c.active_profile||"Default");setPictures(await call("list_backgrounds"))}catch(e){console.error("[jarngrip] status",e)}};
 SP_REACT.useEffect(()=>{refresh()},[]);
 // A backend answer: take its config, or show its error.
 const apply=r=>{if(r&&r.error)setMessage(r.error);else setMessage("");if(r&&r.config){setCfg(r.config);setProfile(r.config.active_profile||"Default");setRemap({combo:null})}return r};
 const toggle=async v=>{apply(await call("set_enabled",v));await refresh()};
 const pickControl=v=>setRemap({control:v,combo:null});
 const writeBinding=async value=>{const bindings={...(cfg.bindings||{})};if(value===null)delete bindings[control];else bindings[control]=value;const r=await saveConfig({...cfg,bindings});if(r.config){setCfg(r.config);setRemap({combo:null})}};
 const isDefault=c=>c.key===gameOf(cfg).defaults[control]&&sortMods(c.mods).join()===sortMods(gameOf(cfg).mods[control]||[]).join();
 const saveMapping=()=>writeBinding(isDefault(combo)?null:[...sortMods(combo.mods),combo.key].join("+"));
 const toggleMod=(m,on)=>setCombo({...combo,mods:on?sortMods([...combo.mods,m]):combo.mods.filter(x=>x!==m)});
 const keyOptions=keyLabel[combo.key]?keyNames.map(([c,n])=>({data:c,label:n})):[{data:combo.key,label:`Key code ${combo.key}`},...keyNames.map(([c,n])=>({data:c,label:n}))];
 // Another game: its own controls and profiles come back (see select_game in main.py).
 const selectGame=async game=>apply(await call("select_game",game));
 const loadProfile=async opt=>{setProfile(opt.data);apply(await call("select_profile",opt.data))};
 const saveProfile=async name=>{const r=apply(await call("save_profile",name));if(r&&r.ok)setNewProfile("")};
 const deleteProfile=async()=>apply(await call("delete_profile",profile));
 const profileOptions=Object.keys(cfg.profiles||{Default:{}}).map(x=>({data:x,label:x}));
 const setSetting=async(key,v)=>{const n={...cfg,[key]:v};setCfg(n);const r=await saveConfig(n);if(r.config)setCfg(r.config);if(r.error)setMessage(r.error)};
 const setSensitivity=v=>setSetting("sensitivity",v);
 const setShortcut=v=>{shortcutOn=v;setSetting("shortcut",v)};
 // Decky's own uninstall, with its confirmation: it calls the backend's _uninstall first, which puts back the bottom
 // screen and the AYN button and removes what JarnGrip installed in the home folder.
 const uninstall=()=>{const loader=window.DeckyPluginLoader;
  if(loader?.uninstallPlugin)loader.uninstallPlugin("JarnGrip","Uninstall JarnGrip","Uninstall","Stops the pad, gives the bottom screen and the AYN button back, and removes JarnGrip. Your settings and profiles are kept.");
  else setMessage("Uninstall JarnGrip from Decky's settings: Plugins, then the menu next to JarnGrip.")};
 const [recordingNow,setRecordingNow]=SP_REACT.useState(false);
 const changeShortcut=async()=>{
  setRecordingNow(true);setMessage("Press the button or buttons for the shortcut, then let go.");
  const masks=await recordShortcut();
  setRecordingNow(false);
  if(!masks){setMessage("No button was seen: Steam does not report that button to plugins. For the AYN button, use the switch below.");return}
  shortcut=masks;setMessage(`Shortcut: ${shortcutText(masks)}`);await setSetting("shortcut_buttons",masks);
 };
 // The few things used every time stay in view; the rest is in sections that open with a tap (Section).
 const themeName=(themeOptions.find(o=>o.data===(({steamos:"charcoal",oled:"dark"})[cfg.theme]||cfg.theme||"classic"))?.label||"Classic").split(" (")[0];
 const remapped=Object.keys(cfg.bindings||{}).length;
 return jsxs("div",{children:[
  jsxs(DFL.PanelSection,{title:"Bottom-screen controls",children:[
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"Enable JarnGrip",description:status.enabled?"The bottom screen pad is active.":"Starts the GTK touch pad in Armada's bottom gamescope session.",checked:!!status.enabled,onChange:toggle})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Status",description:message||status.ayn_error||(status.enabled?`Running • ${gameOf(cfg).short} • profile ${cfg.active_profile||"Default"}`:"Stopped. Bound to the bottom gamescope session.")})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Game",description:"Lays the pad out for this game, or for the desktop and the web. Each keeps its own remapped controls and profiles.",childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:cfg.game||"wow",rgOptions:gameOptions,onChange:opt=>selectGame(opt.data)})})})]}),
  jsx(Section,{id:"opening",title:"Opening the pad",summary:[cfg.shortcut!==false?`Shortcut: ${shortcutText(validShortcut(cfg.shortcut_buttons))}`:"Shortcut off",cfg.ayn_button?(cfg.ayn_no_screenshot?"AYN button, no screenshot":"AYN button"):""].filter(Boolean).join(" · "),children:[
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:`Shortcut: ${shortcutText(validShortcut(cfg.shortcut_buttons))}`,description:"Opens or closes the pad from anywhere, even in a game.",checked:cfg.shortcut!==false,onChange:setShortcut})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",disabled:recordingNow,onClick:changeShortcut,children:recordingNow?"Press it now…":"Change shortcut"})}),
   ...(validShortcut(cfg.shortcut_buttons).join()!==DEFAULT_SHORTCUT.join()?[jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",onClick:()=>{shortcut=DEFAULT_SHORTCUT;setSetting("shortcut_buttons",DEFAULT_SHORTCUT)},children:"Back to Home + Start"})},"reset-shortcut")]:[]),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"AYN button",description:"The AYN button below the screen opens or closes the pad. While it still takes screenshots, so does Home + R1.",checked:!!cfg.ayn_button,onChange:v=>{setAyn({...cfg,ayn_button:v});setSetting("ayn_button",v)}})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"Stop the screenshot",description:"The AYN button sends F24, a key nothing uses, instead of taking a screenshot. It stays that way until you turn this off or uninstall JarnGrip.",checked:!!cfg.ayn_no_screenshot,disabled:!cfg.ayn_button,onChange:v=>{setAyn({...cfg,ayn_no_screenshot:v});setSetting("ayn_no_screenshot",v)}})})]}),
  jsx(Section,{id:"appearance",title:"Appearance and feel",summary:`${themeName} · haptics ${cfg.haptics===false?"off":`${Math.round(100*(cfg.haptics_strength??1))}%`} · trackpad ${Number(cfg.sensitivity||1).toFixed(1)}×`,children:[
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Theme",childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:({steamos:"charcoal",oled:"dark"})[cfg.theme]||cfg.theme||"classic",rgOptions:themeOptions,onChange:opt=>setSetting("theme",opt.data)})})}),
   ...(cfg.theme==="glass"?[
    jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Background picture",description:`Add pictures to ${pictures.folder}, then reopen this menu.`,childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:cfg.background_image||"",rgOptions:[{data:"",label:"Built-in colors"},...pictures.pictures.map(p=>({data:p,label:p}))],onChange:opt=>setSetting("background_image",opt.data)})})},"picture"),
    jsx(DFL.PanelSectionRow,{children:jsx(DFL.SliderField,{label:`Glass blur: ${cfg.glass_blur??3}`,value:Number(cfg.glass_blur??3),min:1,max:5,step:1,showValue:false,onChange:v=>setSetting("glass_blur",v)})},"blur")]:[]),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"Haptics",description:"A short buzz on every button and key press.",checked:cfg.haptics!==false,onChange:v=>setSetting("haptics",v)})}),jsx(DFL.PanelSectionRow,{children:jsx(DFL.SliderField,{label:`Haptic strength: ${Math.round(100*(cfg.haptics_strength??1))}%`,value:Math.round(100*(cfg.haptics_strength??1)),min:10,max:100,step:10,disabled:cfg.haptics===false,onChange:v=>setSetting("haptics_strength",v/100)})}),jsx(DFL.PanelSectionRow,{children:jsx(DFL.SliderField,{label:`Trackpad sensitivity: ${Number(cfg.sensitivity||1).toFixed(1)}×`,description:"How far the pointer moves for a finger's travel on the trackpad.",value:Number(cfg.sensitivity||1),min:.2,max:3,step:.1,showValue:false,onChange:setSensitivity})}),jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"Burn-in protection",description:"Drifts the pad by a pixel or two and dims it after a minute without a touch.",checked:cfg.burn_in!==false,onChange:v=>setSetting("burn_in",v)})}),jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"24-hour clock",checked:!!cfg.clock_24h,onChange:v=>setSetting("clock_24h",v)})}),jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"Start with Desktop Mode",description:"Opens the pad on the bottom screen whenever Desktop Mode starts. Without it, start JarnGrip from the app menu.",checked:!!cfg.desktop_mode,onChange:v=>setSetting("desktop_mode",v)})})]}),
  jsx(Section,{id:"profiles",title:"Profiles",summary:`${cfg.active_profile||"Default"}${profileOptions.length>1?` · ${profileOptions.length} profiles`:""}`,children:[
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Profile",description:"A profile is a saved set of remapped controls and number pad icons.",childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:profile,rgOptions:profileOptions,onChange:loadProfile})})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",onClick:()=>saveProfile(profile),children:`Save current mapping to ${profile}`})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.TextField,{label:"New profile name",value:newProfile,onChange:e=>setNewProfile(e.target.value)})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",disabled:!newProfile.trim(),onClick:()=>saveProfile(newProfile),children:"Save as new profile"})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",disabled:profileOptions.length<2,onClick:deleteProfile,children:`Delete ${profile}`})})]}),
  jsx(Section,{id:"remap",title:"Remap a control",summary:remapped?`${remapped} ${remapped===1?"control":"controls"} remapped`:"Every control on its default key",children:[
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Control",description:`Now sends ${comboText(comboOf(cfg,control))}`,childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:control,rgOptions:controlOptionsOf(cfg),onChange:opt=>pickControl(opt.data)})})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Key",childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:combo.key,rgOptions:keyOptions,onChange:opt=>setCombo({...combo,key:opt.data})})})}),
   ...MODS.map(m=>jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:`With ${m[0].toUpperCase()+m.slice(1)}`,checked:combo.mods.includes(m),onChange:v=>toggleMod(m,v)})},m)),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",onClick:saveMapping,children:`Save: ${comboText(combo)}`})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",onClick:()=>writeBinding(null),children:"Reset to default"})}),
   ...(cfg.game==="desktop"?[]:[jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Number block",description:`Number 1 to number = are the number block. A swipe on a number adds ${gameOf(cfg).swipes[0]} (up) or ${gameOf(cfg).swipes[1]} (left) to what it sends; down cancels it.${cfg.game==="ffxi"?" Ctrl and Alt bring up FFXI's two macro bars.":""}`})},"numbers")])]}),
  ...(cfg.game==="desktop"?[]:[jsx(Section,{id:"icons",title:"Number pad icons",summary:[padModeLabel(cfg),cfg.game==="wow"&&padMode(cfg)!=="numbers"&&cfg.wow_bars!==false?"WoW action bars":""].filter(Boolean).join(" · "),children:[
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Number keys show",description:cfg.game==="wow"?"Spell names: what each key casts in WoW, with the JarnGrip addon, or else its number. Icons: square keys with your own pictures, like a Stream Deck, or else the spell's icon or name. Each profile keeps its own pictures.":"Icons: square keys with your own pictures, like a Stream Deck. Each profile keeps its own pictures.",childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:padMode(cfg),rgOptions:padModeOptions(cfg),onChange:opt=>setSetting("number_pad",opt.data)})})},"numberpad"),
   ...(cfg.game==="wow"?[jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"Use my WoW action bars",description:"With the JarnGrip addon in WoW, a key without a picture of its own shows the icon of what it casts in the game, or its name. See the guide.",checked:cfg.wow_bars!==false,onChange:v=>setSetting("wow_bars",v)})},"wowbars")]:[]),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",onClick:openIconPage,disabled:!api.routerHook,description:api.routerHook?"Opens a full-screen page to pick a picture for each number and its swipes.":"This version of Decky cannot open the icon page. Set the icons in ~/.config/jarngrip/config.json (see the guide).",children:"Edit icons…"})})]},"icons")]),
  jsx(Section,{id:"more",title:"Stop and uninstall",summary:"Give the bottom screen back, or remove JarnGrip",children:[
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",onClick:()=>toggle(false),children:"Stop and restore screen services"})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",onClick:uninstall,children:"Uninstall JarnGrip"})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Desktop Mode safety",description:"Stops with Armada bottom gamescope and never auto-restarts. Turn it back on here or with the shortcut after returning to Game Mode."})})]})
 ]});
}
// The full-screen page for the number pad's icons, opened by "Edit icons…": the twelve numbers laid out as on the pad,
// each showing its tap's picture, and the pictures of the chosen one's tap and swipes beside them. Steam cannot open
// files in the home folder, so the page asks the backend for the pictures it shows (icon_previews), each once.
const ICON_ROUTE="/jarngrip-icons";
const nav=()=>DFL.Navigation||DFL.Router;
const openIconPage=()=>{nav()?.Navigate?.(ICON_ROUTE);nav()?.CloseSideMenus?.()};
const PAGE_STYLE={marginTop:"40px",height:"calc(100% - 40px)",padding:"16px 32px",boxSizing:"border-box",overflowY:"auto",color:"white"};
const SELECTED="#1a9fff";
const PICKER_MAX=120;  // pictures shown at once in the picker: a search narrows a bigger folder down
const PREVIEW_CHUNK=24;  // pictures asked for in one call, one call after another, so that no reply is huge
// Whether a picture's name has every word of a search in it, with its dashes, underscores and dots taken as spaces.
// When the WoW addon last saved the bars, in words.
const ago=seconds=>{const s=Math.max(0,Date.now()/1000-seconds);return s<90?"just now":s<5400?`${Math.round(s/60)} minutes ago`:s<129600?`${Math.round(s/3600)} hours ago`:`${Math.round(s/86400)} days ago`};
const nameMatches=(name,search)=>{const n=name.toLowerCase().replace(/[-_.]+/g," ");return search.toLowerCase().split(/\s+/).filter(Boolean).every(w=>n.includes(w))};
function IconPage(){
 const [cfg,setCfg]=SP_REACT.useState(null);
 const [files,setFiles]=SP_REACT.useState({folder:"",icons:[]});
 const [slot,setSlot]=SP_REACT.useState("slot_1");
 const [message,setMessage]=SP_REACT.useState("");
 const [picking,setPicking]=SP_REACT.useState(null);  // [icon id, what it is] while the picker is open
 const [search,setSearch]=SP_REACT.useState("");
 const [previews,setPreviews]=SP_REACT.useState({});  // file name -> data: URI
 const [bars,setBars]=SP_REACT.useState({file:"",keys:{}});  // what the WoW addon saved of the action bars (wow_bars)
 const asked=SP_REACT.useRef(new Set());  // the names whose previews were asked for
 const load=async()=>{try{asked.current=new Set();setPreviews({});setCfg(await call("get_config"));setFiles(await call("list_icons"));setBars(await call("wow_bars"))}catch(e){console.error("[jarngrip] icons",e);setMessage(String(e))}};
 SP_REACT.useEffect(()=>{load()},[]);
 const matching=()=>files.icons.filter(n=>nameMatches(n,search));
 // The pictures on show, the numbers' and a page of the picker's, are asked for once each, as they come into view.
 const fromWoW=id=>cfg&&cfg.game==="wow"&&cfg.wow_bars!==false?(bars.keys||{})[id]:undefined;
 const onShow=cfg?[...Object.values(cfg.icons||{}),...Object.keys(bars.keys||{}).map(id=>fromWoW(id)?.picture).filter(Boolean),...(picking?matching().slice(0,PICKER_MAX):[])]:[];
 SP_REACT.useEffect(()=>{const wanted=[...new Set(onShow)].filter(n=>files.icons.includes(n)&&!asked.current.has(n));if(!wanted.length)return;
  wanted.forEach(n=>asked.current.add(n));
  // A chunk at a time, each shown as it comes. Those the backend left for another reply ("more") are asked for again.
  (async()=>{for(let i=0;i<wanted.length;i+=PREVIEW_CHUNK){
   try{const r=await call("icon_previews",wanted.slice(i,i+PREVIEW_CHUNK));
    (r.more||[]).forEach(n=>asked.current.delete(n));setPreviews(p=>({...p,...(r.previews||{})}))}
   catch(e){console.error("[jarngrip] previews",e);return}}})()});
 if(!cfg)return jsx("div",{style:PAGE_STYLE,children:message||"Loading…"});
 const icons=cfg.icons||{};
 const saveIcons=async next=>{setCfg({...cfg,icons:next});const r=await call("save_config",{icons:next});if(r.config)setCfg(r.config);setMessage(r.error||"")};
 const setIcon=(id,name)=>{const next={...icons};if(name)next[id]=name;else delete next[id];saveIcons(next)};
 const fill=async()=>{const r=await call("fill_icons");if(r.config)setCfg(r.config);setMessage(r.error||(r.filled?`Filled ${r.filled} ${r.filled===1?"icon":"icons"} from file names.`:"No picture is named for a number. See the naming below."))};
 const pick=name=>{setIcon(picking[0],name);setPicking(null)};
 const clearKey=()=>saveIcons(Object.fromEntries(Object.entries(icons).filter(([id])=>id.split(":")[0]!==slot)));
 const clearAll=()=>saveIcons({});
 // What a number or swipe shows: the picture picked for it, else the one of what its key holds in WoW.
 const shownName=id=>icons[id]||fromWoW(id)?.picture||"";
 const picture=(name,size)=>{const src=name&&previews[name];return src?jsx("img",{src,style:{width:size,height:size,objectFit:"cover",borderRadius:6,display:"block"}}):null};
 const corner=label=>jsx("span",{style:{position:"absolute",top:4,left:6,fontSize:14,lineHeight:"18px",padding:"0 6px",borderRadius:9,background:"rgba(0,0,0,.65)",color:"white"},children:label});
 // The = key is labelled ^ while the addon's Japanese keyboard bindings are on (/jarngrip jis), as on the pad.
 const labelOf=label=>label==="="&&bars.jis&&cfg.game==="wow"&&cfg.wow_bars!==false?"^":label;
 const key=({data,label:own})=>{const label=labelOf(own),name=shownName(data),shown=picture(name,"100%"),caption=icons[data]||fromWoW(data)?.name;
  return jsxs(DFL.DialogButton,{onClick:()=>{setSlot(data);setPicking(null)},style:{width:96,height:96,minWidth:0,padding:0,position:"relative",overflow:"hidden",boxSizing:"border-box",border:`3px solid ${data===slot?SELECTED:"transparent"}`,display:"flex",alignItems:"center",justifyContent:"center"},
   children:shown?[shown,corner(label)]:[jsx("span",{style:{fontSize:34},children:label}),caption?jsx("span",{style:{position:"absolute",bottom:4,left:4,right:4,fontSize:11,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"},children:caption}):null]},data)};
 // The picker: a search, and the pictures that match it as a grid, None first. B or Cancel closes it.
 const picker=()=>{const found=matching(),shown=found.slice(0,PICKER_MAX);
  const tile=(name,caption)=>jsxs(DFL.DialogButton,{onClick:()=>pick(name),autoFocus:!name,style:{minWidth:0,padding:6,height:"auto",boxSizing:"border-box",border:`3px solid ${(icons[picking[0]]||"")===name?SELECTED:"transparent"}`,display:"flex",flexDirection:"column",alignItems:"center",gap:4},
   children:[jsx("div",{style:{width:80,height:80,display:"flex",alignItems:"center",justifyContent:"center",fontSize:12,overflow:"hidden"},children:name?(picture(name,80)||"no preview"):"None"}),jsx("div",{style:{width:"100%",fontSize:11,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"},children:caption})]},name||"none");
  return jsxs(DFL.Focusable,{style:{flex:1,minWidth:0},onCancelButton:()=>setPicking(null),children:[
   jsx("h3",{style:{margin:"0 0 8px"},children:`Picture for ${picking[1]}`}),
   jsx(DFL.TextField,{label:"Search",value:search,onChange:e=>setSearch(e.target.value)}),
   jsx("div",{style:{opacity:.7,fontSize:13,margin:"8px 0"},children:found.length>shown.length?`${found.length} pictures match: the first ${PICKER_MAX} are shown. Search to narrow them down.`:`${found.length} of ${files.icons.length} pictures`}),
   jsx(DFL.Focusable,{style:{display:"grid",gridTemplateColumns:"repeat(auto-fill, minmax(100px, 1fr))",gap:8},children:[tile("",fromWoW(picking[0])?"from WoW":"the number"),...shown.map(n=>tile(n,n))]}),
   jsx(DFL.DialogButton,{onClick:()=>setPicking(null),style:{marginTop:12},children:"Cancel"})]})};
 const swipes=gameOf(cfg).swipes;
 const label=labelOf(numberOptions.find(o=>o.data===slot).label);
 const rows=[["","Tap"],["up",`Swipe up (${swipes[0]})`],["down",`Swipe left (${swipes[1]})`]];
 const box=id=>jsx("div",{style:{width:64,height:64,borderRadius:6,background:"rgba(255,255,255,.08)",display:"flex",alignItems:"center",justifyContent:"center",flex:"none"},children:picture(shownName(id),64)});
 const wow=id=>{const w=fromWoW(id);return w?`From WoW: ${w.name}${w.picture?"":" (no picture of it)"}`:"None (the number)"};
 const barsLine=cfg.game!=="wow"||cfg.wow_bars===false?"":bars.character?`WoW bars: ${bars.character}${bars.spec?` (${bars.spec})`:""}, saved ${ago(bars.saved)}. A picture you pick here wins over WoW's; clear it to show WoW's again.${!bars.icon_list&&Object.values(bars.keys||{}).some(w=>!w.picture)?` Some have no picture: put icon-names.csv in ${files.folder} to match pictures named for WoW's icons (see the guide).`:""}`:bars.file?`WoW bars: ${bars.file} has no action bars in it yet. Type /reload in WoW, or /jarngrip to see what the addon saw.`:"WoW bars: nothing saved yet. Install the JarnGrip addon in WoW, then type /reload in the game (see the guide).";
 return jsxs("div",{style:PAGE_STYLE,children:[
  jsx("h2",{style:{margin:"0 0 4px"},children:`Number pad icons · ${gameOf(cfg).name} · profile ${cfg.active_profile||"Default"}`}),
  jsx("div",{style:{opacity:.7,marginBottom:16},children:message||(padMode(cfg)==="icons"?"Saved as you pick. Save the profile in the JarnGrip panel to keep them with it.":`The number keys show ${padModeLabel(cfg).toLowerCase()}: pick Icons under Number keys show in the JarnGrip panel to see your pictures on the pad.`)}),
  barsLine?jsx("div",{style:{opacity:.7,marginBottom:16,fontSize:13},children:barsLine}):null,
  jsxs("div",{style:{display:"flex",gap:40,alignItems:"flex-start"},children:[
   jsx(DFL.Focusable,{style:{display:"grid",gridTemplateColumns:"repeat(3, 96px)",gap:10,flex:"none"},children:numberOptions.map(key)}),
   picking?picker():jsxs("div",{style:{flex:1,minWidth:0},children:[
    jsx("h3",{style:{margin:"0 0 8px"},children:`Key ${label}`}),
    // A row per tap and swipe: its picture, its name on one line, and the button that picks its picture, which takes
    // the room left and cuts a long name short (a Field would squeeze the name to a letter a line instead).
    ...rows.map(([swipe,text])=>{const id=swipe?`${slot}:${swipe}`:slot,name=icons[id];
     return jsxs("div",{style:{display:"flex",alignItems:"center",gap:12,marginBottom:8},children:[box(id),
      jsx("div",{style:{flex:"none",minWidth:150,whiteSpace:"nowrap"},children:text}),
      jsx(DFL.DialogButton,{onClick:()=>{setSearch("");setPicking([id,`Key ${label} · ${text}`])},style:{flex:1,minWidth:0,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"},children:name?(files.icons.includes(name)?name:`${name} (missing)`):wow(id)})]},id)}),
    // As many buttons a row as fit, so that none goes off the screen.
    jsxs(DFL.Focusable,{style:{display:"grid",gridTemplateColumns:"repeat(auto-fit, minmax(130px, 1fr))",gap:10,marginTop:12},children:[
     [clearKey,`Clear key ${label}`],[clearAll,"Clear all"],[fill,"Fill from file names"],[load,"Look for new pictures"],
     [()=>nav()?.NavigateBack?.(),"Done"]].map(([onClick,text])=>jsx(DFL.DialogButton,{onClick,style:{minWidth:0,padding:"8px 10px",whiteSpace:"normal",lineHeight:1.2},children:text},text))}),
    jsx("div",{style:{opacity:.6,fontSize:13,marginTop:16},children:`Pictures: ${files.folder}. PNG, JPEG or WebP, ideally square; one that is not is cut to the square in its middle. Pictures over 256 KB are listed by name, without a preview.`}),
    jsx("div",{style:{opacity:.6,fontSize:13,marginTop:8},children:`Fill from file names puts a picture named for a number, and maybe a swipe, on it: the number (1 to 9, 0, minus or equals), then up, left, ${swipes[0].toLowerCase()} or ${swipes[1].toLowerCase()}, then anything: 5-fireball.png, 5-${swipes[0].toLowerCase()}-frostbolt.png, minus-left.png.`})]})]})]});
}
export default function(){
 // The icon page is a route of its own, full screen, like Decky's settings.
 api.routerHook?.addRoute?.(ICON_ROUTE,IconPage,{exact:true});
 const input=window.SteamClient?.Input?.RegisterForControllerStateChanges?.(onControllerState);
 // The backend toggles the pad for the AYN button itself, and says so here for the toast.
 const onToggled=r=>api.toaster?.toast({title:"JarnGrip",body:r?.error||(r?.enabled?"Pad on":"Pad off")});
 api.addEventListener?.("jarngrip_toggled",onToggled);
 call("get_config").then(c=>{shortcutOn=c.shortcut!==false;shortcut=validShortcut(c.shortcut_buttons);setAyn(c)}).catch(()=>{});
 return {name:"JarnGrip",content:jsx(Content,{}),icon:jsx("svg",{xmlns:"http://www.w3.org/2000/svg",viewBox:"0 0 24 24",width:24,height:24,fill:"none",stroke:"currentColor",strokeWidth:2,children:jsxs("g",{children:[jsx("path",{d:"M14 4 20 2l-2 6-9 9-4-4 9-9Z"}),jsx("path",{d:"m7 14-4 7 7-4M15 5l4 4"})]})}),onDismount(){input?.unregister?.();api.routerHook?.removeRoute?.(ICON_ROUTE);api.removeEventListener?.("jarngrip_toggled",onToggled)}}}
