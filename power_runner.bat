powershell -NoProfile -Command "$p='app\sources\nse_shareholding.py'; $s=Get-Content $p -Raw; $old=@'
            total_shares = _extract_total_shares(xml_bytes)

            if total_shares is None or total_shares <= 0:
                return []

            row = latest["row"]
'@; $new=@'
            total_shares = _extract_total_shares(xml_bytes)

            if total_shares is None or total_shares <= 0:
                return []

            snapshot = _extract_shareholding_snapshot(xml_bytes)

            row = latest["row"]
'@; if(-not $s.Contains($old)){throw 'Latest-only anchor not found'}; $s=$s.Replace($old,$new); $old2='                total_shares=total_shares,`r`n            )'; $new2='                total_shares=total_shares,`r`n                **_snapshot_kwargs(snapshot),`r`n            )'; $count=([regex]::Matches($s,[regex]::Escape($old2))).Count; if($count -ne 2){throw \"Expected 2 constructor targets, found $count\"}; $s=$s.Replace($old2,$new2); $s=$s.Replace('            if total_shares is None or total_shares <= 0:`r`n                continue`r`n`r`n            submission_date = _parse_date(', '            if total_shares is None or total_shares <= 0:`r`n                continue`r`n`r`n            snapshot = _extract_shareholding_snapshot(xml_bytes)`r`n`r`n            submission_date = _parse_date('); Set-Content $p $s -Encoding UTF8"
