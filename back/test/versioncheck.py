import torch
print(torch.version.cuda)          # PyTorch 빌드에 사용된 CUDA 버전
print(torch.cuda.is_available())   # CUDA 사용 가능 여부
print(torch.cuda.get_device_name(0))  # GPU 이름 (GPU가 있다면)

