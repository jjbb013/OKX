# 确保strategies是一个Python包
from pathlib import Path

# 确保必要的目录存在
PATH = Path(__file__).parent
PATH.joinpath('templates').mkdir(exist_ok=True)
PATH.joinpath('static').mkdir(exist_ok=True)
PATH.joinpath('strategies').mkdir(exist_ok=True)