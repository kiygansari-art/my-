# Railway ga deploy
1. Papkani GitHub reposiga yuklang (git init, git add ., git commit, git push).
2. railway.app -> New Project -> Deploy from GitHub repo -> reponi tanlang.
3. Railway Procfile'ni avtomatik taniydi. Settings -> Networking -> Generate Domain.
4. Chek rasmlari va baza saqlanib qolishi uchun: Volume qo'shing (mount: /data), Variables: DATA_DIR=/data
5. Admin kirish: Nastroyka -> Familiya: isakov, Ism: isakov (keyin Admin panelda o'zgartiring).
