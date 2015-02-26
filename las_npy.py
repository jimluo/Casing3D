#!/usr/bin/env  python
#coding:utf8
import os
import os.path
import yaml
from math import ceil
from io import StringIO
import numpy as np
from scipy.interpolate import InterpolatedUnivariateSpline
from PyQt5 import QtCore, QtGui
from PyQt5.QtGui import QPixmap, QIcon, QImage, QPainter

W_INTERP = 80
mtdtype = ('T1', ('T16', 'T12'))
mfctype = ('R1', ('R56','R40','R24'))

def frange(start, stop, step):
    while start < stop:
        yield start
        start += step

def utf8(s):
    return s
    # return QtCore.QString.fromUtf8(s)

def readfile(fname, win=None):
    if not os.path.exists(fname):
        msgbox(win, '错误', '没找到文件 %s' % fname)
        return False
    f = open(fname, 'r')
    s = f.read()
    f.close()
    return s

def readyaml(fname, win=None):
    if not os.path.exists(fname):
        msgbox(win, '错误', '没找到文件 %s' % fname)
        return False
    f = open(fname, 'r')
    s = yaml.load(f)
    f.close()
    return s

def writeyaml(fname, mydict):
    f = open(fname, 'w')
    f.write(yaml.dump(mydict))
    f.close()

def list_npz_name(ext):
    return [n for n in os.listdir('.') if n.endswith(ext)]

def msgbox(win, title, msg):
    QtGui.QMessageBox.critical(win, utf8(title), utf8(msg))

def import_las(win, ui_files, is_interpre=False):
    fname = QtWidgets.QFileDialog.getOpenFileName(win, utf8('打开LAS文件'), '', '*.las')
    if fname:
        fname = las2npy_nointerpre(unicode(fname)) if is_interpre else las2npz(unicode(fname))
        if fname.startswith('ERR'):
            msgbox(win, '警告', fname[4:])
        else:
            ui_files.addItem(fname)
            return fname

def tofloat(d):
    try:
        return float(d)
    except:
        return 0.0

def readlas(fname):
    las = readfile(fname)

    lashead, data = las.split('~A')
    data = data[data.find('\n')+1:-1] #remove first line, curves comment
    lashead, parameters = lashead.split('~P')
    head, curve = lashead.split('~C')
    depth = [float(n.split(':')[-2].split()[-1]) for n in head.split('\n') if 'STRT' in n or 'STOP' in n or 'STEP' in n]
    curves = [c.split('.')[0].strip() for c in curve.split('\n') if not c.startswith('#') and ':' in c]
    start, stop, step = depth
    data = np.fromiter((tofloat(d) for d in data.split()), dtype='float32')
    print(len(data), len(curves), len(data)/len(curves))
    numrow, numcol = int(ceil(abs((stop - start)/step)+0.5)), len(curves)
    if numrow * numcol != len(data):
        print(numrow, numcol, len(data), len(data)/len(curves), depth)
        return 'ERR LAS文件中曲线数量或深度有误，例如不能有~Paramter参数，~Curve之后必须是~Ascii'

    data = data.reshape((numrow, numcol))
    return lashead, data, depth, curves

def find_tool_range(data, curves):
    mtdtype = ('T1', ('T16', 'T12'))
    mfctype, RBname = ('R1', ('R56','R40','R24')), ('RB', 'Slope') #gowell MFC
    is_warrior_las = False
    if 'FING01' in curves: #sondex MIT
        mfctype, RBname = ('FING01', ('FING56','FING40','FING24')), ('RB', 'DEV')
        try:
            dep, idxOD, idxTHK= np.loadtxt('casing.txt')
            is_warrior_las = True
        except:
            raise Exception('ERR WARRIOR LAS 无casing.txt文件或文件内容错误')
    else:
        try:
            # idxOD, idxTHK = curves.index('OD'),  curves.index('THK')
            dep, idxOD, idxTHK= np.loadtxt('casing.txt')
            is_warrior_las = True
        except:
            raise Exception('ERR AXP LAS 文件中没有找到 OD THK曲线')
    try:
        idxRB, idxDEV = curves.index(RBname[0]), curves.index(RBname[1])
    except:
        idxRB, idxDEV = -1, -1

    idxODmax = curves.index('MaxDia') if 'MaxDia' in curves else curves.index('IDMX') if 'IDMX' in curves else -1
    idxTHKmax = curves.index('Tmax') if 'Tmax' in curves else curves.index('Tmax') if 'Tmax' in curves else -1

    print("idxOD=%d, idxTHK=%d, idxRB=%d, idxDEV=%d, idxODmax=%d, idxTHKmax=%d" % (idxOD, idxTHK, idxRB, idxDEV, idxODmax, idxTHKmax))

    toolrange = [[-1,-1], [-1,-1]]
    for i, (c, stopname) in enumerate((mfctype, mtdtype)):
        if c in curves:
            for n in stopname:
                if n in curves:
                    begin, end = curves.index(c), curves.index(n)
                    toolrange[i] = [begin, end]
                    print(c, begin, end)

    numrow, numcol = data.shape
    dataNone = np.zeros((1,numrow),dtype='float32').T
    OD = np.repeat(idxOD, numrow).reshape(numrow, 1) if is_warrior_las else data[:, idxOD:idxOD+1]
    THK = np.repeat(idxTHK, numrow).reshape(numrow, 1) if is_warrior_las else data[:, idxTHK:idxTHK+1]
    RB = data[:, idxRB:idxRB+1] if idxRB > 0 else dataNone
    DEV = data[:, idxDEV:idxDEV+1] if idxRB > 0 else dataNone
    casingdata = np.hstack((RB, DEV, OD, THK))
    return toolrange, casingdata, idxODmax, idxTHKmax

def las2npz(fname):
    lashead, data, depth, curves = readlas(fname)
    try:
        toolrange, casingdata, idxODmax, idxTHKmax  = find_tool_range(data, curves)
    except Exception as s:
        return str(s)
    RB, DEV, OD, THK = 0,1,2,3
    OR = casingdata[:, OD] / 2.0
    IR = OR - casingdata[:, THK]
    nullarray = np.array([], dtype=np.float32).reshape((0,0))

    (mfcbegin, mfcend), (mtdbegin, mtdend) = toolrange
    dataTool = [
            nullarray if mfcbegin == -1 else data[:,mfcbegin:mfcend+1],
            nullarray if mtdbegin == -1 else data[:,mtdbegin:mtdend+1]]

    #3次样条插值到稀疏的仪器数据阵列
    #x_new = np.arange(0,W_INTERP*dataTool[0].shape[0])
    MFC, MTD = 0, 1
    dataSpline = [nullarray, nullarray]
    x_new = np.arange(0,W_INTERP)
    color = readyaml('casing3D.yml')['color']
    for i, base, gain, clr in zip((MFC, MTD), (IR, OR), (2, 4), color):
        d = dataTool[i]
        print('spline idx, base, gain', i, base[0], gain)
        if d.shape[0] > 0:
            x_old = np.linspace(0,W_INTERP, d.shape[1])
            # print d, OR
            if i == MTD and d.shape[0] == OR.shape[0]:
                d = (d + IR[0] - OR[0]) * gain + OR[0] # mtd增大厚度变化
            d = np.vstack([InterpolatedUnivariateSpline(x_old, row)(x_new) for row in d])
            dataSpline[i] = d.astype('float32')

    fname = os.path.split(fname)[-1]
    fname, ext = os.path.splitext(fname)
    fname = fname + '.npz'
    np.savez(fname,
        depth=np.array(depth),
        casingdata=casingdata,
        mfc=dataTool[MFC],
        mtd=dataTool[MTD],
        mfcSpline=dataSpline[MFC],
        mtdSpline=dataSpline[MTD])

    return fname

def las2npy_nointerpre(fname):
    lashead, data, depth, curves = readlas(fname)
    try:
        toolrange, casingdata, idxODmax, idxTHKmax  = find_tool_range(data, curves)
    except Exception as s:
        return str(s)

    fname = os.path.split(fname)[-1]
    fname, ext = os.path.splitext(fname)
    fname = fname + '.2.npz'
    np.savez(fname,
        depth=np.array(depth),
        lashead = lashead,
        casingdata = casingdata,
        curves = curves,
        data = data,
        maxtool = (idxODmax, idxTHKmax),
        toolrange = toolrange)

    return fname

def npy2las(data, lashead, fname):
    las = StringIO()
    np.savetxt(las, data, '%12.2f')
    f = open(fname + '.las', 'w')
    f.write(str(lashead) + '~A\n')
    f.write(las.getvalue())
    las.close()
    f.close()

#test
#fname=las2npy('t.las')
#fname = 't.npy'
#data=np.load(fname)
#name, ext = os.path.splitext(os.path.basename(fname))
#yml = yaml.load(open(name + '.yml', 'r'))
#npy2las(data, yml, 't.npy')
