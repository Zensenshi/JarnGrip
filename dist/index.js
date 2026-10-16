// SPDX-License-Identifier: GPL-3.0-only
const manifest={name:"JarnGrip"};
const init=window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if(!init)throw new Error("Decky Loader API unavailable");
let api;try{api=init.connect(2,manifest.name)}catch{api=init.connect(1,manifest.name)}
const call=api.call, jsx=SP_JSX.jsx, jsxs=SP_JSX.jsxs;
// Control ids and their default Linux key codes, as in driver/bin/pad_model.py.
const defaults={character:46,spellbook:25,talents:49,quest_log:38,map:50,social:24,guild:36,group_finder:23,achievements:21,professions:37,bags:48,system:1,self:59,party_1:60,party_2:61,party_3:62,party_4:63,next_enemy:15,previous_enemy:15,sheathe_weapons:44,auto_run:69,walk_run:98,sit_stand:45,hide_ui:44,enemy_nameplates:47,friendly_nameplates:47,chat_page_up:104,chat_page_down:109,screenshot:99,slot_1:2,slot_2:3,slot_3:4,slot_4:5,slot_5:6,slot_6:7,slot_7:8,slot_8:9,slot_9:10,slot_10:11,slot_11:12,slot_12:13};
// The controls that send a modifier with their key by default.
const defaultMods={previous_enemy:["shift"],hide_ui:["alt"],friendly_nameplates:["shift"]};
const controlOptions=Object.keys(defaults).map(x=>({data:x,label:x.replaceAll("_"," ")}));
// The key picker: [Linux key code, name].
const keyNames=[[30,"A"],[48,"B"],[46,"C"],[32,"D"],[18,"E"],[33,"F"],[34,"G"],[35,"H"],[23,"I"],[36,"J"],[37,"K"],[38,"L"],[50,"M"],[49,"N"],[24,"O"],[25,"P"],[16,"Q"],[19,"R"],[31,"S"],[20,"T"],[22,"U"],[47,"V"],[17,"W"],[45,"X"],[21,"Y"],[44,"Z"],[11,"0"],[2,"1"],[3,"2"],[4,"3"],[5,"4"],[6,"5"],[7,"6"],[8,"7"],[9,"8"],[10,"9"],[59,"F1"],[60,"F2"],[61,"F3"],[62,"F4"],[63,"F5"],[64,"F6"],[65,"F7"],[66,"F8"],[67,"F9"],[68,"F10"],[87,"F11"],[88,"F12"],[1,"Esc"],[15,"Tab"],[57,"Space"],[28,"Enter"],[14,"Backspace"],[58,"Caps Lock"],[103,"Up"],[108,"Down"],[105,"Left"],[106,"Right"],[110,"Insert"],[111,"Delete"],[102,"Home"],[107,"End"],[104,"Page Up"],[109,"Page Down"],[12,"-"],[13,"="],[26,"["],[27,"]"],[39,";"],[40,"'"],[41,"`"],[43,"\\"],[51,","],[52,"."],[53,"/"],[82,"Numpad 0"],[79,"Numpad 1"],[80,"Numpad 2"],[81,"Numpad 3"],[75,"Numpad 4"],[76,"Numpad 5"],[77,"Numpad 6"],[71,"Numpad 7"],[72,"Numpad 8"],[73,"Numpad 9"],[98,"Numpad /"],[55,"Numpad *"],[74,"Numpad -"],[78,"Numpad +"],[83,"Numpad ."],[96,"Numpad Enter"],[69,"Num Lock"],[99,"Print Screen"],[70,"Scroll Lock"],[119,"Pause"],[42,"Left Shift"],[29,"Left Ctrl"],[56,"Left Alt"],[54,"Right Shift"],[97,"Right Ctrl"],[100,"Right Alt"]];
const keyLabel=Object.fromEntries(keyNames);
const MODS=["ctrl","shift","alt"];
const sortMods=mods=>MODS.filter(m=>mods.includes(m));
// What a control sends, as {key, mods}: the binding saved for it (a number keeps the default modifiers, text such as
// "shift+15" is the whole combination), or its default. The same rules as combo_for in driver/bin/pad_model.py.
const comboOf=(cfg,control)=>{const v=(cfg.bindings||{})[control],mods=defaultMods[control]||[];
 if(typeof v==="number"&&v>0&&v<248)return {key:v,mods};
 if(typeof v==="string"){const parts=v.toLowerCase().split("+").map(x=>x.trim()),key=Number(parts.pop());if(key>0&&key<248&&parts.every(p=>MODS.includes(p)))return {key,mods:sortMods(parts)}}
 return {key:defaults[control],mods}};
const comboText=c=>[...sortMods(c.mods).map(m=>m[0].toUpperCase()+m.slice(1)),keyLabel[c.key]||`key code ${c.key}`].join(" + ");
// Theme ids as in driver/bin/pad_model.py.
const themeOptions=[{data:"classic",label:"Classic (stone and gold)"},{data:"charcoal",label:"Charcoal (slate and blue)"},{data:"dark",label:"Dark (pure black)"},{data:"glass",label:"Game Glass (your picture)"}];
function Content(){
 const [status,setStatus]=SP_REACT.useState({enabled:false});
 const [cfg,setCfg]=SP_REACT.useState({bindings:{},profiles:{},active_profile:"Default",sensitivity:1,theme:"classic",haptics:true,haptics_strength:1,burn_in:true,clock_24h:false,desktop_mode:false});
 const [control,setControl]=SP_REACT.useState("character");
 const [combo,setCombo]=SP_REACT.useState({key:46,mods:[]});
 const [profile,setProfile]=SP_REACT.useState("Default");
 const [newProfile,setNewProfile]=SP_REACT.useState("");
 const [message,setMessage]=SP_REACT.useState("");
 const [pictures,setPictures]=SP_REACT.useState({folder:"~/Pictures/JarnGrip",pictures:[]});
 const refresh=async()=>{try{const s=await call("get_status"),c=await call("get_config");setStatus(s);setCfg(c);setProfile(c.active_profile||"Default");setCombo(comboOf(c,control));setPictures(await call("list_backgrounds"))}catch(e){console.error("[jarngrip] status",e)}};
 SP_REACT.useEffect(()=>{refresh()},[]);
 // A backend answer: take its config, or show its error.
 const apply=r=>{if(r&&r.error)setMessage(r.error);else setMessage("");if(r&&r.config){setCfg(r.config);setProfile(r.config.active_profile||"Default");setCombo(comboOf(r.config,control))}return r};
 const toggle=async v=>{apply(await call("set_enabled",v));await refresh()};
 const pickControl=v=>{setControl(v);setCombo(comboOf(cfg,v))};
 const writeBinding=async value=>{const bindings={...(cfg.bindings||{})};if(value===null)delete bindings[control];else bindings[control]=value;const r=await call("save_config",{...cfg,bindings});if(r.config){setCfg(r.config);setCombo(comboOf(r.config,control))}};
 const isDefault=c=>c.key===defaults[control]&&sortMods(c.mods).join()===sortMods(defaultMods[control]||[]).join();
 const saveMapping=()=>writeBinding(isDefault(combo)?null:[...sortMods(combo.mods),combo.key].join("+"));
 const toggleMod=(m,on)=>setCombo({...combo,mods:on?sortMods([...combo.mods,m]):combo.mods.filter(x=>x!==m)});
 const keyOptions=keyLabel[combo.key]?keyNames.map(([c,n])=>({data:c,label:n})):[{data:combo.key,label:`Key code ${combo.key}`},...keyNames.map(([c,n])=>({data:c,label:n}))];
 const loadProfile=async opt=>{setProfile(opt.data);apply(await call("select_profile",opt.data))};
 const saveProfile=async name=>{const r=apply(await call("save_profile",name));if(r&&r.ok)setNewProfile("")};
 const deleteProfile=async()=>apply(await call("delete_profile",profile));
 const profileOptions=Object.keys(cfg.profiles||{Default:{}}).map(x=>({data:x,label:x}));
 const setSetting=async(key,v)=>{const n={...cfg,[key]:v};setCfg(n);const r=await call("save_config",n);if(r.config)setCfg(r.config)};
 const setSensitivity=v=>setSetting("sensitivity",v);
 return jsxs(DFL.PanelSection,{title:"Bottom-screen controls",children:[
  jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"Enable JarnGrip",description:status.enabled?"The bottom screen pad is active.":"Starts the GTK touch pad in Armada's bottom gamescope session.",checked:!!status.enabled,onChange:toggle})}),
  jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Status",description:message||(status.enabled?`Running • profile ${cfg.active_profile||"Default"}`:"Stopped. Bound to the bottom gamescope session.")})}),
  jsxs(DFL.PanelSection,{title:"Appearance and feel",children:[jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Theme",childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:({steamos:"charcoal",oled:"dark"})[cfg.theme]||cfg.theme||"classic",rgOptions:themeOptions,onChange:opt=>setSetting("theme",opt.data)})})}),
   ...(cfg.theme==="glass"?[
    jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Background picture",description:`Add pictures to ${pictures.folder}, then reopen this menu.`,childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:cfg.background_image||"",rgOptions:[{data:"",label:"Built-in colors"},...pictures.pictures.map(p=>({data:p,label:p}))],onChange:opt=>setSetting("background_image",opt.data)})})},"picture"),
    jsx(DFL.PanelSectionRow,{children:jsx(DFL.SliderField,{label:`Glass blur: ${cfg.glass_blur??3}`,value:Number(cfg.glass_blur??3),min:1,max:5,step:1,showValue:false,onChange:v=>setSetting("glass_blur",v)})},"blur")]:[]),jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"Haptics",description:"A short buzz on every button and key press.",checked:cfg.haptics!==false,onChange:v=>setSetting("haptics",v)})}),jsx(DFL.PanelSectionRow,{children:jsx(DFL.SliderField,{label:`Haptic strength: ${Math.round(100*(cfg.haptics_strength??1))}%`,value:Math.round(100*(cfg.haptics_strength??1)),min:10,max:100,step:10,disabled:cfg.haptics===false,onChange:v=>setSetting("haptics_strength",v/100)})}),jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"Burn-in protection",description:"Drifts the pad by a pixel or two and dims it after a minute without a touch.",checked:cfg.burn_in!==false,onChange:v=>setSetting("burn_in",v)})}),jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"24-hour clock",checked:!!cfg.clock_24h,onChange:v=>setSetting("clock_24h",v)})}),jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:"Start with Desktop Mode",description:"Opens the pad on the bottom screen whenever Desktop Mode starts. Without it, start JarnGrip from the app menu.",checked:!!cfg.desktop_mode,onChange:v=>setSetting("desktop_mode",v)})})]}),
  jsxs(DFL.PanelSection,{title:"Profiles",children:[
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Profile",description:"A profile is a saved set of remapped controls.",childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:profile,rgOptions:profileOptions,onChange:loadProfile})})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",onClick:()=>saveProfile(profile),children:`Save current mapping to ${profile}`})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.TextField,{label:"New profile name",value:newProfile,onChange:e=>setNewProfile(e.target.value)})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",disabled:!newProfile.trim(),onClick:()=>saveProfile(newProfile),children:"Save as new profile"})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",disabled:profileOptions.length<2,onClick:deleteProfile,children:`Delete ${profile}`})})]}),
  jsxs(DFL.PanelSection,{title:"Remap a control",children:[
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Control",description:`Now sends ${comboText(comboOf(cfg,control))}`,childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:control,rgOptions:controlOptions,onChange:opt=>pickControl(opt.data)})})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Key",childrenLayout:"below",childrenContainerWidth:"max",children:jsx(DFL.Dropdown,{selectedOption:combo.key,rgOptions:keyOptions,onChange:opt=>setCombo({...combo,key:opt.data})})})}),
   ...MODS.map(m=>jsx(DFL.PanelSectionRow,{children:jsx(DFL.ToggleField,{label:`With ${m[0].toUpperCase()+m.slice(1)}`,checked:combo.mods.includes(m),onChange:v=>toggleMod(m,v)})},m)),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",onClick:saveMapping,children:`Save: ${comboText(combo)}`})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",onClick:()=>writeBinding(null),children:"Reset to default"})}),
   jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Number block",description:"Slots 1 to 12 are the number block. A swipe on a number adds Shift (up) or Ctrl (down) to what it sends; left cancels it."})})]}),
  jsx(DFL.PanelSectionRow,{children:jsx(DFL.SliderField,{label:`Trackpad sensitivity: ${Number(cfg.sensitivity||1).toFixed(1)}×`,value:Number(cfg.sensitivity||1),min:.2,max:3,step:.1,showValue:true,onChange:setSensitivity})}),
  jsx(DFL.PanelSectionRow,{children:jsx(DFL.ButtonItem,{layout:"below",onClick:()=>toggle(false),children:"Stop and restore screen services"})}),
  jsx(DFL.PanelSectionRow,{children:jsx(DFL.Field,{label:"Desktop Mode safety",description:"Stops with Armada bottom gamescope and never auto-restarts. Re-enable from Decky after returning to Game Mode."})})
 ]});
}
export default function(){return {name:"JarnGrip",content:jsx(Content,{}),icon:jsx("svg",{xmlns:"http://www.w3.org/2000/svg",viewBox:"0 0 24 24",width:24,height:24,fill:"none",stroke:"currentColor",strokeWidth:2,children:jsxs("g",{children:[jsx("path",{d:"M14 4 20 2l-2 6-9 9-4-4 9-9Z"}),jsx("path",{d:"m7 14-4 7 7-4M15 5l4 4"})]})}),onDismount(){}}}
