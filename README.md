# Devstick
> PRoot kullanarak taşınabilir Linux ortamları oluşturun

## İndirme
```bash
git clone https://github.com/yaso09/devstick.git

cd devstick
```

## Bağımlılıkları Kurma
```bash
uv sync
python update_repos.py
```

## Derleme
```bash
uv run pyinstaller devstick.spec
```
Çıktı `dist/devstick` klasörüne oluşacaktır.
