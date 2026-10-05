"""Localización y envoltura de FFmpeg. Implementación en MVP 1.

Todo el post-proceso (trim, concat, crop 9:16, xfade, setpts, sidechaincompress,
NVENC) pasa por aquí; los módulos de engines/video y engines/audio no invocan
FFmpeg directamente.
"""
