-- SPDX-License-Identifier: GPL-3.0-only
-- JarnGrip: saves what each key on your action bars reaches (the spell, item or macro on the button it is bound to,
-- and the icon WoW shows for it) for the JarnGrip touch pad, which shows them on its number keys.
--
-- It reads your key bindings and your action bars. It sends no keys and presses no buttons. The one thing it changes,
-- and only when you turn it on with /jarngrip jis, is what a few keys do in this session (see JIS below): your saved
-- key bindings stay as they are.
-- WoW itself writes what it saved to WTF/Account/<account>/SavedVariables/JarnGrip.lua when you log out, exit the
-- game or type /reload; the pad reads that file from the disk afterwards.

local ADDON = ...

-- The default action bars: a binding's command, and the buttons it presses. A button knows the action slot it shows
-- (bar 1 follows its page, stance and form); the first slot of each bar is there in case a button cannot say.
local BARS = {
  ACTIONBUTTON = { "ActionButton", 1 },
  MULTIACTIONBAR1BUTTON = { "MultiBarBottomLeftButton", 61 },
  MULTIACTIONBAR2BUTTON = { "MultiBarBottomRightButton", 49 },
  MULTIACTIONBAR3BUTTON = { "MultiBarRightButton", 25 },
  MULTIACTIONBAR4BUTTON = { "MultiBarLeftButton", 37 },
  MULTIACTIONBAR5BUTTON = { "MultiBar5Button", 145 },
  MULTIACTIONBAR6BUTTON = { "MultiBar6Button", 157 },
  MULTIACTIONBAR7BUTTON = { "MultiBar7Button", 169 },
}

-- The keys looked at, with each mix of modifiers, in the order WoW writes them (ALT-CTRL-SHIFT-1). The pad's numbers
-- send 1 to 0, - and = with Shift or Ctrl; the rest are there for numbers remapped to other keys.
local MODIFIERS = { "", "SHIFT-", "CTRL-", "ALT-", "CTRL-SHIFT-", "ALT-SHIFT-", "ALT-CTRL-", "ALT-CTRL-SHIFT-" }
local KEYS = { "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "[", "]", ";", "'", "`", "\\", ",", ".",
  "/", "SPACE", "TAB", "BACKSPACE", "ENTER", "HOME", "END", "PAGEUP", "PAGEDOWN", "INSERT", "DELETE", "UP", "DOWN",
  "LEFT", "RIGHT", "NUMPADDECIMAL", "NUMPADMINUS", "NUMPADPLUS", "NUMPADMULTIPLY", "NUMPADDIVIDE" }
for letter in ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):gmatch(".") do KEYS[#KEYS + 1] = letter end
for i = 1, 12 do KEYS[#KEYS + 1] = "F" .. i end
for i = 0, 9 do KEYS[#KEYS + 1] = "NUMPAD" .. i end

-- The action slot a button shows: Blizzard's bars, or a bar addon's (Bartender, ElvUI and Dominos buttons say which
-- slot they show in one of these ways).
local function buttonSlot(frame)
  if type(frame) ~= "table" then return nil end
  if frame._state_type == "action" and type(frame._state_action) == "number" then return frame._state_action end
  if type(frame.action) == "number" and frame.action > 0 then return frame.action end
  if frame.GetAttribute then
    local slot = tonumber(frame:GetAttribute("action"))
    if slot and slot > 0 then return slot end
  end
  return nil
end

-- The action slot a binding's command presses, or nil for a command that is not an action button.
local function slotOf(command)
  local clicked = command:match("^CLICK (.+):[^:]*$")
  if clicked then return buttonSlot(_G[clicked]) end
  local bar, n = command:match("^(.-BUTTON)(%d+)$")
  local frames = bar and BARS[bar]
  if not frames then return nil end
  n = tonumber(n)
  return buttonSlot(_G[frames[1] .. n]) or (frames[2] + n - 1)
end

-- Key bindings made on a Japanese (JIS, 106/109 key) keyboard, for a game that reads its keys as a US keyboard does
-- (Proton on the pad's handheld): each pair is the US key and the JIS key in the same place, so that = does what ^
-- does, with whatever modifiers. WoW's override bindings do it: they last for the session, are never saved or synced
-- with the account, and are set again at each login. Turned on per WoW install (JarnGripDB.jis, in the install's own
-- SavedVariables), so a desktop with the JIS keyboard is left alone.
local JIS = { { "=", "^" }, { "[", "@" }, { "]", "[" }, { "'", ":" }, { "\\", "]" } }
local owner = CreateFrame("Frame")
local mirrored = ""  -- the overrides in place, as text, to tell when they need setting again

local function mirror()
  local wanted, parts = {}, {}
  if JarnGripDB.jis then
    for _, modifier in ipairs(MODIFIERS) do
      for _, pair in ipairs(JIS) do
        local command = GetBindingAction(modifier .. pair[2])  -- the saved binding, never an override
        if command and command ~= "" then
          wanted[#wanted + 1] = { modifier .. pair[1], command }
          parts[#parts + 1] = modifier .. pair[1] .. " " .. command
        end
      end
    end
  end
  local text = table.concat(parts, "\n")
  if text == mirrored then return end  -- setting them again would fire UPDATE_BINDINGS, and so on for ever
  ClearOverrideBindings(owner)
  for _, each in ipairs(wanted) do
    local button, mouse = each[2]:match("^CLICK (.+):([^:]+)$")
    if button then
      SetOverrideBindingClick(owner, false, each[1], button, mouse)
    else
      SetOverrideBinding(owner, false, each[1], each[2])
    end
  end
  mirrored = text
end

local function spellName(id)
  if C_Spell and C_Spell.GetSpellName then return C_Spell.GetSpellName(id) end
  if GetSpellInfo then return (GetSpellInfo(id)) end
end

-- Whether an item on the bars had no name yet the last time: WoW loads items' names on demand, and says so with
-- GET_ITEM_INFO_RECEIVED. That event comes for every item the game loads (bags, tooltips, loot, the auction house),
-- so the bars are only read again for it while one of theirs is still waiting.
local waitingForItems = false

local function itemName(id)
  local name
  if C_Item and C_Item.GetItemNameByID then
    name = C_Item.GetItemNameByID(id)
  elseif GetItemInfo then
    name = GetItemInfo(id)
  end
  if not name then waitingForItems = true end
  return name
end

-- What an action slot holds: { name, icon, kind }, or nil when it is empty. icon is the file id WoW shows (a path in
-- older clients).
local function describe(slot)
  if not HasAction(slot) then return nil end
  local kind, id = GetActionInfo(slot)
  local name
  if kind == "spell" then
    name = spellName(id)
  elseif kind == "item" then
    name = itemName(id)
  elseif kind == "macro" then
    name = GetActionText(slot)
  elseif kind == "summonmount" and C_MountJournal and C_MountJournal.GetMountInfoByID then
    name = C_MountJournal.GetMountInfoByID(id)
  elseif kind == "flyout" and GetFlyoutInfo then
    name = GetFlyoutInfo(id)
  elseif kind == "equipmentset" then
    name = id
  end
  if type(name) ~= "string" or name == "" then name = GetActionText(slot) end
  if type(name) ~= "string" or name == "" then return nil end
  return { name = name, icon = GetActionTexture(slot), kind = kind }
end

local function specName()
  if GetSpecialization and GetSpecializationInfo then
    local index = GetSpecialization()
    if index then return select(2, GetSpecializationInfo(index)) end
  end
end

local waitingForCombat = false
local lastCount = 0

-- What WoW read from the disk when the game started (ADDON_LOADED): the file the pad sees until WoW writes it again.
-- When the bars read at login differ from it (the game was last closed without logging out, from Steam's menu say,
-- or the character is another one), a popup offers to reload, which writes the file, so the pad need not wait for
-- a /reload typed by hand. Checked once a session, once item names have loaded or after a few tries.
local onDisk
local loginCheck = "waiting"  -- "waiting" for PLAYER_ENTERING_WORLD, then "ready", then "done"
local loginTries = 0

local function sameEntry(a, b)
  return type(a) == "table" and type(b) == "table" and a.name == b.name and a.icon == b.icon and a.kind == b.kind
end

local function sameKeys(a, b)
  if type(a) ~= "table" or type(b) ~= "table" then return false end
  for combo, entry in pairs(a) do
    if not sameEntry(entry, b[combo]) then return false end
  end
  for combo in pairs(b) do
    if a[combo] == nil then return false end
  end
  return true
end

StaticPopupDialogs.JARNGRIP_RELOAD = {
  text = "JarnGrip: your action bars are not saved for the pad yet (WoW saves them when you log out or reload).\n\n"
    .. "Reload now?",
  button1 = RELOADUI or "Reload",
  button2 = NOT_NOW or LATER or "Not now",
  OnAccept = function() ReloadUI() end,
  timeout = 0,
  whileDead = true,
  hideOnEscape = true,
  preferredIndex = 3,
}

local function checkLogin(who, keys)
  if loginCheck ~= "ready" then return end
  loginTries = loginTries + 1
  if waitingForItems and loginTries < 5 then return end  -- an item's name still loading would look like a change
  loginCheck = "done"
  local saved = onDisk and onDisk.characters[who]
  if onDisk and onDisk.last == who and type(saved) == "table" and sameKeys(saved.keys, keys) then return end
  StaticPopup_Show("JARNGRIP_RELOAD")
end

local function save()
  -- During combat the bars cannot change, and some of what is read here is hidden from addons: wait until it ends.
  if InCombatLockdown() then
    waitingForCombat = true
    return
  end
  mirror()  -- first, so that what is saved for = is what it does now
  local keys, count = {}, 0
  waitingForItems = false
  for _, modifier in ipairs(MODIFIERS) do
    for _, key in ipairs(KEYS) do
      local combo = modifier .. key
      local command = GetBindingAction(combo, true)
      if command and command ~= "" then
        local slot = slotOf(command)
        local entry
        if slot then
          entry = describe(slot)
        elseif not command:find("^CLICK ") and _G["BINDING_NAME_" .. command] then
          entry = { name = _G["BINDING_NAME_" .. command], kind = "binding" }  -- a key bound to Map, Autorun, ...
        end
        if entry then
          keys[combo] = entry
          count = count + 1
        end
      end
    end
  end
  local who = (UnitName("player") or "?") .. " - " .. (GetRealmName() or "?")
  JarnGripDB.characters[who] = { keys = keys, spec = specName(), class = UnitClass("player"), saved = time() }
  JarnGripDB.last = who
  JarnGripDB.jis = JarnGripDB.jis == true  -- the pad labels its = key ^ when this is on
  lastCount = count
  if count > 0 then checkLogin(who, keys) end
end

local function trySave()
  local ok, err = pcall(save)
  if not ok then JarnGripDB.error = tostring(err) end
end

-- Bars change a slot at a time: one save a second after the last change.
local queued = false
local function queue()
  if queued then return end
  queued = true
  C_Timer.After(1, function()
    queued = false
    trySave()
  end)
end

local frame = CreateFrame("Frame")
frame:SetScript("OnEvent", function(_, event, name)
  if event == "ADDON_LOADED" then
    if name ~= ADDON then return end
    if type(JarnGripDB) ~= "table" then JarnGripDB = {} end
    if type(JarnGripDB.characters) ~= "table" then JarnGripDB.characters = {} end
    JarnGripDB.version = 1
    JarnGripDB.error = nil
    local characters = {}
    for who, entry in pairs(JarnGripDB.characters) do characters[who] = entry end  -- save() replaces, never edits
    onDisk = { last = JarnGripDB.last, characters = characters }
  elseif event == "PLAYER_ENTERING_WORLD" then
    if loginCheck == "waiting" then loginCheck = "ready" end
    if JarnGripDB then queue() end
  elseif event == "PLAYER_REGEN_ENABLED" then
    if waitingForCombat then
      waitingForCombat = false
      queue()
    end
  elseif event == "PLAYER_LOGOUT" then
    trySave()
  elseif event == "GET_ITEM_INFO_RECEIVED" then
    if waitingForItems and JarnGripDB then queue() end
  elseif JarnGripDB then
    queue()
  end
end)
-- Some of these are not in every version of the game: one that is missing is left out.
for _, event in ipairs({ "ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD", "PLAYER_LOGOUT",
  "PLAYER_REGEN_ENABLED", "ACTIONBAR_SLOT_CHANGED", "ACTIONBAR_PAGE_CHANGED", "UPDATE_BONUS_ACTIONBAR",
  "UPDATE_BINDINGS", "PLAYER_SPECIALIZATION_CHANGED", "ACTIVE_TALENT_GROUP_CHANGED", "GET_ITEM_INFO_RECEIVED",
  "UPDATE_MACROS" }) do
  pcall(frame.RegisterEvent, frame, event)
end

SLASH_JARNGRIP1 = "/jarngrip"
SlashCmdList.JARNGRIP = function(message)
  local word, value = (message or ""):lower():match("^%s*(%S*)%s*(%S*)")
  if word == "jis" then
    if InCombatLockdown() then
      print("|cffd4a017JarnGrip|r: not during combat. Try again after it.")
      return
    end
    if value == "on" then JarnGripDB.jis = true elseif value == "off" then JarnGripDB.jis = false
    else JarnGripDB.jis = not JarnGripDB.jis end
    trySave()
    print(JarnGripDB.jis
      and ("|cffd4a017JarnGrip|r: Japanese keyboard bindings on, in this WoW install only: = does what ^ does, [ what @ "
        .. "does, ] what [ does, ' what : does and \\ what ] does, with Shift, Ctrl or Alt too. Your key bindings "
        .. "are not changed.")
      or "|cffd4a017JarnGrip|r: Japanese keyboard bindings off.")
    StaticPopup_Show("JARNGRIP_RELOAD")  -- so that the pad reads it
    return
  end
  trySave()
  print(("|cffd4a017JarnGrip|r: %d keys of your action bars saved for the pad. WoW writes them to disk when you log "
    .. "out or type /reload."):format(lastCount))
  if JarnGripDB.error then print("|cffd4a017JarnGrip|r: " .. JarnGripDB.error) end
end
