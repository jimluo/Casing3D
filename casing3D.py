#!/usr/bin/env  python
#coding:utf8

import sys
from math import pi, cos, sin, ceil
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
# from PyQt4 import QtCore, QtGui, QtOpenGL
from PyQt5 import QtCore, QtWidgets, QtOpenGL
from PyQt5.QtGui import QPixmap, QIcon, QImage, QPainter, QBrush, QColor
from ui_casing3D import Ui_casing3D
from las_npy import import_las, list_npz_name, readyaml, writeyaml, W_INTERP, utf8

MFC, MTD, DAT, DEP, CLIP, APART, BACK = 0, 1, 2, 3, 4, 5, 6
RB, DEV, OD, THK = 0, 1, 2, 3

CASING_MFC = 1
CASING_MTD = 2
DATA_DEP = 3
DATA_MFC = 4
DATA_MTD = 5
AXIS = 6

DISP_LEN = 200 #screen pixels for 1 casing

class Casing3D(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(Casing3D, self).__init__(parent)
        translator = QtCore.QTranslator()
        translator.load("casing3D.qm")
        app.installTranslator(translator)
        self.ui = Ui_casing3D()
        self.ui.setupUi(self)

        self.cfg = readyaml('casing3D.yml')
        self.ui.files.addItems(list_npz_name('.npz'))

        self.glWidget = GLWidget(self, self.cfg['color'])
        self.ui.hGL.insertWidget(0, self.glWidget)
        self.ui.hGL.setStretch(0, 77)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(100)

        self.init_color()

    def init_color(self):
        diff = (50,40,30,20,10,0,-10,-20,-30,-40,-50)
        for tbl, color in zip((self.ui.mfcColor, self.ui.mtdColor), self.cfg['color']):
            tbl.clear()
            for i, (r,g,b) in enumerate(color):
                tbl.insertRow(i)
                tbl.setItem(i, 0, QtWidgets.QTableWidgetItem(str(diff[i])))
                tbl.setItem(i, 1, QtWidgets.QTableWidgetItem(''))
                tbl.item(i, 1).setBackground(QBrush(QColor.fromRgbF(r,g,b)))

    def on_color_click(self, row, col):
        if col == 1:
            color = QtGui.QColorDialog.getColor(parent = self)
            if color.isValid():
                self.sender().item(row, 1).setBackgroundColor(QtGui.QColor(color))

    def on_colorOk_click(self):
        self.cfg['color'] = [[], []]
        for i, tbl in enumerate((self.ui.mfcColor, self.ui.mtdColor)):
            for row in range(tbl.rowCount()):
                r,g,b = tbl.item(row, 1).backgroundColor().getRgbF()[:-1]
                self.cfg['color'][i].append([r,g,b])
        writeyaml('casing3D.yml', self.cfg)
        self.glWidget.update_color(self.cfg['color'])

    def on_colorReset_click(self):
        c = [[0.5, 0.0, 0.0], #50
             [1.0, 0.0, 0.0],#40
             [1.0, 0.5, 0.0],  #30
             [1.0, 1.0, 0.0],  #20
             [0.5, 1.0, 0.0],#10
             [0.0, 1.0, 0.0],  #0
             [0.0, 1.0, 0.5],#-10
             [0.0, 1.0, 1.0],  #-20
             [0.0, 0.5, 1.0],  #-30
             [0.0, 0.0, 1.0],  #-40
             [0.0, 0.0, 0.5]]  #-50
        self.cfg['color'] = [c, c]
        self.init_color()
        self.glWidget.update_color(self.cfg['color'])

    def on_set_depth(self, dep):
        self.glWidget.update_depth(dep)

    def on_change_depth(self, value):
        self.ui.depth.setValue(self.ui.depSelect.value())

    def on_depth_len_change(self, length):
        self.glWidget.update_data_len(length)

    def on_auto_depth(self, ischecked):
        def repeat_grow_depth():
            gl = self.glWidget
            dep = start + gl.data_idx * step
            self.ui.depth.setValue(dep)
            gl.data_idx += 2
            if gl.data_idx >= gl.data[DAT].shape[0] - gl.data_len:
                self.timer.stop()
                self.ui.auto_depth.Checked(False)

        start, stop, step = self.glWidget.depth
        if ischecked:
            self.timer.timeout.connect(repeat_grow_depth)
            self.timer.start()
        else:
            self.timer.stop()

    def on_savebmp_click(self):
        pixmap = self.glWidget.grabFrameBuffer()
        files = self.ui.files
        fname = files.item(files.currentRow()).text() + '.jpg'
        if not pixmap.save(fname, 'JPG'):
            print('jpg not save')

    def on_viewport_click(self, ischecked):
        self.glWidget.rotation = [0,0,0] if self.sender() == self.ui.viewfront else [0,-90,90]
        self.glWidget.updateGL()

    def on_show_click(self, ischecked):
        ui = self.ui
        senders = [ui.showMFC,ui.showMTD,ui.showData,ui.showDep,ui.showClip,ui.showApart,ui.showBack]
        self.glWidget.show[senders.index(self.sender())] = ischecked
        self.glWidget.updateGL()
        self.glWidget.updateGL()

    def on_files_change(self, fname):
        if hasattr(self, 'glWidget'):
            npz = np.load(str(fname))
            #d, self.depth, datarange = npz['data'], npz['depth'], npz['range']
            self.depth = npz['depth']
            d = npz['casingdata']
            mfc, mtd = npz['mfc'], npz['mtd']
            mfc_s, mtd_s = npz['mfcSpline'].astype('float32'), npz['mtdSpline'].astype('float32')

            start, stop, step = self.depth
            depLength = int(ceil(abs(start - stop))) - 1
            self.ui.dispLength.setMaximum(depLength)
            self.ui.gbDepth.setTitle(utf8('深度(米)[%d~%d:%d]' % (start, stop, depLength)))
            self.ui.showMFC.setChecked(mfc.shape[0] > 10)
            self.ui.showMTD.setChecked(mtd.shape[0] > 10)

            ID = d[:, OD] - d[:, THK] * 2
            self.glWidget.update_data(self.depth, [mfc, mtd, d], [mfc_s, mtd_s], ID)

            if step < 0:
                start, stop = stop, start
            self.ui.depth.setRange(start, stop)
            self.ui.depth.setValue(stop)
            self.ui.depSelect.setRange(start, stop)
            self.ui.depSelect.setValue(stop)

    def on_import_las(self):
        self.ui.importLAS.setText(utf8('请稍等...'))
        fname = import_las(self, self.ui.files)
        self.on_files_change(fname)
        self.ui.importLAS.setText(utf8('导入LAS'))

class GLWidget(QtOpenGL.QGLWidget):
    def __init__(self, parent, color):
        super(GLWidget, self).__init__(QtOpenGL.QGLFormat(QtOpenGL.QGL.SampleBuffers), parent)

        self.parent = parent
        self.color = np.array(color) #MFC,MTD
        self.scalexy = 0.010
        self.scalez = 0.010
        self.show = [True, True, False, False, False, False, True] #MFC, MTD, DAT, DEP, CLIP, APART, BACK
        self.depth = [0.0, 0.0, 1/40.0] #start, stop, step
        self.data = None
        self.tools = []
        self.rotation = [-45,-45,0] #X,Y,Z
        self.data_idx = 0

        idxs = []
        for i in range(DISP_LEN-1):
            for j in range(W_INTERP):
                idxs.append((i*W_INTERP+j, i*W_INTERP+j+W_INTERP))
            idxs.append((i*W_INTERP, i*W_INTERP+W_INTERP))

        self.idxs = np.array(idxs).reshape(2*(W_INTERP+1)*(DISP_LEN-1)) #glDrawElements(vector indices)
        z = np.linspace(DISP_LEN / 2, -DISP_LEN / 2.0, DISP_LEN)
        self.verts_z = np.repeat(z, W_INTERP).reshape(DISP_LEN*W_INTERP, 1) #glDrawElements(vector(x,y,Z))

    def update_data(self, depth, data, interp_data, ID, color=None):
        if color != None:
            self.color = np.array(color)
        self.data = data#MFC, MTD, ALL
        self.interp_data = interp_data
        self.tools = [i for i, d in enumerate(interp_data) if d.shape[0] > 0]
        print(self.tools, len(interp_data), interp_data[0].shape)
        #RB, DEV, OD, THK = 0, 1, 2, 3

        self.ID = ID
        self.depth = depth
        d = self.data[DAT]
        h = d.shape[0]
        OR = (d[:,OD] / 2.0).reshape((h,1))
        IR = OR - d[:,THK].reshape((h, 1))
        T = d[:,THK].reshape((h, 1))
        self.diffcolor = [None, None]
        for i in self.tools:
            rows = self.interp_data[i]
            base, gain = (IR, OR)[i], (1, 3)[i]
            diff = np.round((rows-base)/(T*gain)*10).astype('int')
            np.place(diff, diff > 5, 5)
            np.place(diff, diff < -5, -5)
            self.diffcolor[i] = 5 - diff

        self.angle = [0, 0]
        for i in self.tools:
            num = self.data[i].shape[1]
            theta= 2.0 * pi / num
            self.angle[i] = [(cos(j * theta), sin(j * theta)) for j in range(num)]
        theta = 2.0 * pi / W_INTERP
        self.angleSpline = np.array([(cos(i * theta), sin(i * theta)) for i in range(W_INTERP)], dtype='float32')

        self.rotation = [-45,-45,0] #X,Y,Z
        self.data_idx = 0
        self.update_data_len(20) #以20米为单位

    def update_color(self, color):
        self.color = np.array(color)
        if self.data != None:
            self.build_all()

    def _make_data_draw(self):
        start, step = self.data_idx, self.data_step
        idx = np.linspace(0, DISP_LEN * step, DISP_LEN).astype('int') + start
        #print idx.shape, idx[0], idx[-1], self.interp_data[0].shape, self.interp_data[1].shape
        self.data_draw = [None, None]
        h = self.verts_z.shape[0]
        for i in self.tools:#MFC.MTD
            rows = self.interp_data[i][idx]
            diff, clr = self.diffcolor[i], self.color[i]
            diff = diff[idx].flatten()
            x, y = rows*self.angleSpline[:,0], rows*self.angleSpline[:,1]
            verts = np.hstack((x.reshape(h,1), y.reshape(h,1), self.verts_z))
            rgb = clr[diff]
            self.data_draw[i] = (verts.flatten(), rgb.flatten())

    def update_data_len(self, length):
        dep_len = abs(self.depth[1] - self.depth[0])
        length = min(length, dep_len)
        dep_step = abs(self.depth[2])
        self.data_len = length / dep_step #一屏显示深度点数
        self.data_step = self.data_len / float(DISP_LEN)#每一像素点多少米
        self._make_data_draw()
        self.build_all()

    def update_depth(self, dep):
        start, stop, step = self.depth
        idx = int((dep - start) / step)
        if idx > 0 and idx < abs((start - stop) / step) - self.data_len:
            self.data_idx = idx
            self._make_data_draw()
        self.build_all()

    def initializeGL(self):
        glClearColor(0,0,0,1)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_NORMALIZE)
        glEnable(GL_COLOR_MATERIAL)
        glShadeModel(GL_SMOOTH)
        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL) # surface
        # glShadeModel(GL_SMOOTH)
        glEnable(GL_LIGHTING)
        glLightfv(GL_LIGHT0, GL_POSITION,  (0, 0, 1000, 0))
        glLightfv(GL_LIGHT0, GL_AMBIENT, (0.4, 0.4, 0.4, 1.0))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.6, 0.6, 0.6, 1.0))
        glLightfv(GL_LIGHT0, GL_SPECULAR, (0.2, 0.2, 0.2, 1.0))
        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT1, GL_POSITION,  (1000, 1000, 0, 0))
        # glLightfv(GL_LIGHT1, GL_AMBIENT, (0.4, 0.4, 0.4, 1.0))
        glLightfv(GL_LIGHT1, GL_DIFFUSE, (0.6, 0.6, 0.6, 1.0))
        glLightfv(GL_LIGHT1, GL_SPECULAR, (0.2, 0.2, 0.2, 1.0))
        glLightf( GL_LIGHT1, GL_SPOT_EXPONENT,  3.0);
        glLightf( GL_LIGHT0, GL_SPOT_CUTOFF,    20.0);
        glLightf( GL_LIGHT0, GL_CONSTANT_ATTENUATION, 0.5);
        glLightf( GL_LIGHT0, GL_LINEAR_ATTENUATION, 1.0);
        glLightf( GL_LIGHT0, GL_QUADRATIC_ATTENUATION, 1.5)
        glEnable(GL_LIGHT1)
        glMaterialfv(GL_FRONT, GL_AMBIENT_AND_DIFFUSE, (0.5, 0, 0.3, 1))
        glMaterialfv(GL_FRONT, GL_SPECULAR, (1, 1, 1, 1))
        glMaterialf(GL_FRONT, GL_SHININESS, 60)

    def paintGL(self):
        w, h = self.width(), self.height()
        #3D
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(0, 0, -15)#self.camera_distance)
        x, y, z = self.rotation
        glRotatef(x, 1.0, 0.0, 0.0)
        glRotatef(y, 0.0, 1.0, 0.0)
        glRotatef(z, 0.0, 0.0, 1.0)
        glScale(self.scalexy, self.scalexy, self.scalez)

        if self.show[CLIP]:
            glClipPlane(GL_CLIP_PLANE0, (0.0, 1.0, 0.0, 0.0))
            glEnable(GL_CLIP_PLANE0)
        else:
            glDisable(GL_CLIP_PLANE0)
        if self.show[APART]:
            glTranslatef(0, -100, -15)#self.camera_distance)
        if self.show[MFC]:
            glCallList(CASING_MFC)
        if self.show[APART]:
            glTranslatef(0, 200, -15)#self.camera_distance)
        if self.show[MTD]:
            glCallList(CASING_MTD)

        if self.show[BACK]:
            glClearColor(0.0,0.0,0.0,1.0)
            glColor3d(1,1,1)          # set text color
        else:
            glClearColor(1,1,1,1)
            glColor3d(0,0,0)          # set text color

        glDisable(GL_LIGHTING)
        if self.show[DEP]:
            glCallList(DATA_DEP)
        if self.show[DAT]:
            if self.show[MFC]:
                glCallList(DATA_MFC)
            if self.show[MTD]:
                glCallList(DATA_MTD)
        glEnable(GL_LIGHTING)
        glCallList(AXIS)

        #2D
        glPushMatrix()                     # save current modelview matrix
        glLoadIdentity()                   # reset modelview matrix
        glMatrixMode(GL_PROJECTION)     # switch to projection matrix
        glPushMatrix()                  # save current projection matrix
        glLoadIdentity()                # reset projection matrix
        gluOrtho2D(0, w, 0, h)      # left,right,down,top; set to orthogonal projection

        glDisable(GL_LIGHTING)     # need to disable lighting for proper text color
        self.draw_well_info(w, h)
        self.draw_color_map(w, h)
        glEnable(GL_LIGHTING)

        glPopMatrix()                   # restore to previous projection matrix
        glMatrixMode(GL_MODELVIEW)      # switch to modelview matrix
        glPopMatrix()                   # restore to previous modelview matrix

    def resizeGL(self, width, height):
        aspect = float(width)/float(height)
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glFrustum(-aspect, aspect, -1.0, 1.0, 5.0, 20.0);
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        #glTranslated(0.0, 0.0, -10.0)

    def _depth(self, idx=None):
        start, stop, step = self.parent.depth
        if idx == None:
            idx = self.data_idx
        dep = start + idx * step
        return dep

    def _maxminave(self, datatype, idx=None):
        data = self.data[datatype]
        if idx == None:
            idx = self.data_idx
        if data.shape[0] > 0:
            d = data[idx]
            return np.max(d), np.min(d), np.average(d)
        return 0.0, 0.0, 0.0

    def wheelEvent(self, event):
        idx = self.data_idx - abs(event.delta())/event.delta() * 30
        if idx > 0 and idx < len(self.data[DAT]) - self.data_len:
            self.data_idx = idx
            self.parent.ui.depth.setValue(self._depth())

    def mousePressEvent(self, event):
        self.lastPos = event.pos()

    def mouseMoveEvent(self, event):
        dx = event.x() - self.lastPos.x()
        dy = event.y() - self.lastPos.y()
        self.lastPos = event.pos()
        if event.buttons() & QtCore.Qt.LeftButton:
            if event.buttons() & QtCore.Qt.RightButton:
                self.rotation[2] = (self.rotation[2] + dy) % (360*16) #x
            else:
                self.rotation[0] = (self.rotation[0] + dy) % (360*16) #x
                self.rotation[1] = (self.rotation[1] + dx) % (360*16) #y
        elif event.buttons() & QtCore.Qt.RightButton:
            self.scalexy += (dx + dy) / 20000.0
        elif event.buttons() & QtCore.Qt.MiddleButton:
            self.scalez += (dx + dy) / 20000.0

        self.updateGL()

    def draw_well_info(self, w, h):
        if self.data != None:
            d = self.data[DAT][self.data_idx]
            Dmax, Dmin, Davg = self._maxminave(MFC)
            Tmax, Tmin, Tavg = self._maxminave(MTD)
            deplen = round(self.data_len*abs(self.depth[2]))
            infos = (
                'Depth: %.2f m' % self._depth(), 'Length: %d m' % (int(deplen)), '',
                'Rotation: %d deg' % d[RB], 'Deviation: %d deg' % d[DEV], '',
                'Nom ID: %.1f mm' % (d[OD] - d[THK] * 2), 'Nom OD: %.1f mm' % d[OD], 'Nom THK: %.1f mm' % d[THK],
                'Max ID: %.1f mm' % Dmax, 'Min ID: %.1f mm' % Dmin, 'Avg ID: %.1f mm' % Davg,
                'Max Thk: %.1f mm' % Tmax, 'Min Thk: %.1f mm' % Tmin, 'Avg Thk: %.1f mm' % Tavg)
            self._draw_string_list([(i%3 * 100, h - (i/3)*10-10, None, s) for i, s in enumerate(infos)])

    def draw_color_map(self, w, h):
        for i in self.tools:
            color, x, title = self.color[i], (80, 30)[i], ('MFC', 'MTD')[i]
            strlist = [(w-x+5, 150+20, None, title)]
            diff = ('50','40','30','20','10','0','-10','-20','-30','-40','-50')
            glBegin(GL_QUAD_STRIP)
            for i,(r,g,b) in enumerate(color):
                y = 150 - i * 12
                glColor3f(r, g, b)
                glVertex3f(w - x, y, 0)
                glVertex3f(w - x - 20, y, 0)
                strlist.append((w-x+5, y, None, diff[i]))
            glEnd()
            self._draw_string_list(strlist)

    def _draw_string_list(self, strlist, is3D=False):
        if is3D:
            for x,y,z,s in strlist:
                glRasterPos3fv((x,y,z))        # place text position
                for c in s:
                    glutBitmapCharacter(GLUT_BITMAP_HELVETICA_10, ord(c))
        else:
            if self.show[BACK]:
                glColor3d(1,1,1)
            else:
                glColor3d(0,0,0)
            for x,y,z,s in strlist:
                glRasterPos2f(x, y)        # place text position
                for c in s:
                    glutBitmapCharacter(GLUT_BITMAP_HELVETICA_10, ord(c))

    def build_all(self):
        self.build_casing(CASING_MFC)
        self.build_casing(CASING_MTD)
        self.build_data_depth()
        self.build_data_tool()
        self.build_xyz_axis()
        self.updateGL()

    def build_xyz_axis(self):
        glNewList(AXIS, GL_COMPILE)
        glBegin(GL_LINES)
        glColor3d(1,0,0); glVertex3d(0,0,0); glVertex3d(10,0,0)#red a
        glColor3d(0,1,0); glVertex3d(0,0,0); glVertex3d(0,10,0)#cylin l
        glColor3d(0,0,1); glVertex3d(0,0,0); glVertex3d(0,0,10)#blue b
        glEnd()
        glEndList()

    def build_data_tool(self):
        outd = self.data[DAT][self.data_idx][OD] / 2.5
        z = DISP_LEN / 2.0
        for i in self.tools:
            id_data, data, angle, line_start, line_stop = (DATA_MFC, DATA_MTD)[i], self.data[i], self.angle[i], (-2, 1)[i], (2, 4)[i]
            glNewList(id_data, GL_COMPILE)
            if data != None:
                strlist = []
                for d, (x,y) in zip(data[self.data_idx], angle):
                    glBegin(GL_LINES)
                    start, stop = d + line_start + outd, d + line_stop + outd,
                    glVertex3f(start * x, start * y, z)
                    glVertex3f(stop * x, stop * y, z)
                    glEnd()
                    sign_x, sign_y = 0 if x > 0 else -3, 0 if y > 0 else -3
                    strlist.append((stop*x+sign_x, stop*y+sign_y, z, '%.1f' % d))
                self._draw_string_list(strlist, True)
            glEndList()

    def build_data_depth(self):
        z = DISP_LEN / 2
        print( ' build_data_depth', self.tools, self.data_idx, OD)
        x = self.data[DAT][self.data_idx][OD] / 2.0
        idx = self.data_idx
        strlist = []
        glNewList(DATA_DEP, GL_COMPILE)
        for i in range(11):
            glBegin(GL_LINES); glVertex3f(x+12, 0, z); glVertex3f(x+18, 0, z); glEnd()
            strlist.append((x+20, 0, z, '%.1f' % self._depth(idx + i * self.data_len / 10)))
            glBegin(GL_LINES); glVertex3f(-x-12, 0, z); glVertex3f(-x-18, 0, z); glEnd()
            strlist.append((-x-40, 0, z, '%.1f' % self._depth(idx + i * self.data_len / 10)))
            z -= DISP_LEN / 10
        self._draw_string_list(strlist, True)
        glEndList()

    def build_casing(self, data_type):
        if self.data_draw[data_type-1] != None:
            verts, colors = self.data_draw[data_type-1]
            #GL_VERTEX_ARRAY:vertx(x,y,z)[...], GL_COLOR_ARRAY:colors(r,g,b[x,y,z])[...]
            glNewList(data_type, GL_COMPILE)
            glEnableClientState(GL_NORMAL_ARRAY)
            glEnableClientState(GL_VERTEX_ARRAY)
            glEnableClientState(GL_COLOR_ARRAY)

            glNormalPointer(GL_FLOAT, 0, verts)
            glVertexPointer(3, GL_DOUBLE, 0, verts)
            glColorPointer(3, GL_DOUBLE, 0, colors)
            glDrawElements(GL_QUAD_STRIP, len(self.idxs), GL_UNSIGNED_INT, self.idxs)

            #first MFC finger point
            glPointSize(5)
            glBegin(GL_POINTS)
            glColor3d(1, 0, 0)
            glVertex3f(verts[0], verts[1], verts[2])
            glEnd()

            glDisableClientState(GL_NORMAL_ARRAY)
            glDisableClientState(GL_VERTEX_ARRAY)
            glDisableClientState(GL_COLOR_ARRAY)
            glEndList()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    casing = Casing3D()
    casing.show()
    sys.exit(app.exec_())
