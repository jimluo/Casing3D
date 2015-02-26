 #-*- mode: python -*-

a = Analysis([os.path.join(HOMEPATH,'support\\_mountzlib.py'), os.path.join(HOMEPATH,'support\\useUnicode.py'), 'casing3D.py'],
    excludes=['multiprocessing', 'Pyrex', '_tkinter', 'nose', '_ssl', 'numpy.core._dotblas', 'scipy.linalg._flinalg', 'OpengGL.arrays.vbo'],
    hookspath=['D:\\projects\\axp\\interpretation\\PyInstaller\\hooks'])
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
	  a.binaries,
	  a.zipfiles,
	  a.datas,
	  #exclude_binaries=1,
          name=os.path.join('build\\pyi.win32\\casing3D', 'casing3D.exe'),
          debug=False,
          strip=None,
          upx=True,
          console=False,
	  icon='image\\nemo.ico' )
#app = BUNDLE(exe, name=os.path.join('dist', 'casing3d.exe.app'))
coll = COLLECT( exe,
	       a.binaries,
	       a.zipfiles,
	       a.datas,
	       strip=False,
	       upx=True,
	       name=os.path.join('dist', 'casing3D'))
