on run argv
  set needle to item 1 of argv
  tell application "Google Chrome"
    if (count of windows) is 0 then return ""
    repeat with w in windows
      repeat with t in tabs of w
        if (URL of t as text) contains needle then
          return execute t javascript "(function(){var h=document.documentElement.innerHTML; var i=h.indexOf(\"hlsAuto\"); if(i<0) return \"|||\"; return h.substring(i, i+450) + \"|||\" + document.title;})()"
        end if
      end repeat
    end repeat
  end tell
  return ""
end run
