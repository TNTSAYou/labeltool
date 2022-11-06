# -*- coding: utf-8 -*-
import sys
import os
if hasattr(sys, 'frozen'):
    os.environ['PATH'] = sys._MEIPASS + ";" + os.environ['PATH']
from PyQt5.QtWidgets import *
from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import copy
import xml.etree.cElementTree as et
import os
import cv2
import math
from PIL import Image
import random

# ui配置文件
cUi, cBase = uic.loadUiType("image_widget.ui")

# 主界面
class CImageWidget(QWidget, cUi):
    def __init__(self):
        # 设置UI
        QMainWindow.__init__(self)
        cUi.__init__(self)
        self.setupUi(self)
        
        self.setMouseTracking(True)
        self.setCursor(Qt.UpArrowCursor)   

        #image信息
        self.img_path = ''
        self.img_name = ''
        self.img = None

        # 已标注信息
        self.box_list = []

        #待标注信息
        self.current_class = 0
        self.start_label = False
        self.current_box = [0,0,0,0,0]
        
        #显示信息
        self.det_color = [QColor(255, 0, 0),
                          QColor(0, 255, 0),
                          QColor(0, 255, 255),
                          QColor(255, 0, 255),
                          QColor(0, 255, 255)]
        self.det_width = 2
        self.line_color = QColor(255, 255, 0)
        self.line_width = 1

        #当前鼠标信息
        self.current_x = 0
        self.current_y = 0
        
        #是否切换为快速模式
        self.toggle_fast = False
        
        #快速模式下的相关参数
        self.base_box = []
        self.base_center = []
        
        #是否切换到修改模式
        self.toggle_fixup = False
        
        #当前要修改的检测框
        self.base_label = 0
        self.base_leak_rec = []

        
    def closeEvent(self, event):
        pass
    
    
    def change_fast(self, base_box):
        self.toggle_fast = not self.toggle_fast
        if self.toggle_fast:
            self.base_box = base_box
            # 这里默认0为烟雾框，1为源点框,移动的时候跟随源点框的移动而移动 (x,y)
            self.base_center = [(base_box[1][0]+base_box[1][2])/2, (base_box[1][1]+base_box[1][3])/2]
        else:
            self.toggle_fast = False
            pass
    
    def change_base_box(self, base_box):
        self.base_box = base_box
        # 这里默认0为烟雾框，1为源点框,移动的时候跟随源点框的移动而移动 (x,y)
        self.base_center = [(base_box[1][0]+base_box[1][2])/2, (base_box[1][1]+base_box[1][3])/2]
        
    def change_fixup(self, base_label):
        self.toggle_fixup = not self.toggle_fixup
        if self.toggle_fixup:
            self.base_label = base_label  
        else:
            pass
        
    def change_base_label(self, base_label, base_leak_rec = None):
        if base_label >= len(self.box_list):
            return
        self.base_leak_rec = base_leak_rec
        self.base_label = base_label
        
    def set_info(self, image_path, box_list=None):
        if image_path is None:
            self.img_path = ''
            self.img_name = ''
            self.img = None
            self.box_list = []
            self.start_label = False
            self.current_box = [0, 0, 0, 0, 0]
        else:
            self.img_path = image_path
            self.img_name = os.path.basename(image_path) #.split('.')[0]
            
            #self.img = QPixmap(self.img_path)            
            img_cv = cv2.imread(self.img_path)
            height, width, depth = img_cv.shape
            img_cv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
            qimage_temp = QImage(img_cv.data, width, height, width * depth, QImage.Format_RGB888)
            self.img = QPixmap.fromImage(qimage_temp)
            
            
            if box_list is not None:
                self.box_list = box_list
            else:
                self.box_list = []
        self.update() # 重绘事件，也就是触发paintEvent函数。

    def set_current_cls(self, cls):
        self.current_box[4] = cls

    def get_info(self):
        # filter the area < 10
        flit_box_list = []
        for box in self.box_list:
            x1 = float(box[0])
            y1 = float(box[1])
            x2 = float(box[2])
            y2 = float(box[3])
            area = (x2-x1) * (y2-y1)
            if area > 10.0:
                flit_box_list.append(box)
        return self.img_name, flit_box_list

    def draw_background(self, painter):
        pen = QPen()
        pen.setColor(QColor(0, 0, 0))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(0, 0, self.width(), self.height())

    def draw_image(self, painter):
        if self.img is not None:
            #print(self.img.width(), self.img.height())
            painter.drawPixmap(QtCore.QRect(0, 0, self.width(), self.height()), self.img)
            #painter.drawPixmap(QtCore.QRect(0, 0, self.img.width(), self.img.height()), self.img)
            painter.drawText(10,20,str(self.img_name))

    def draw_det_info(self, painter):
        for rect in self.box_list:
            pen = QPen()
            pen.setColor(self.det_color[int(rect[4]) % len(self.det_color)])
            pen.setWidth(self.det_width)
            painter.setPen(pen)
            painter.drawRect(rect[0] * self.width() / self.img.width(),
                             rect[1] * self.height() / self.img.height(),
                             (rect[2]-rect[0]) * self.width() / self.img.width(),
                             (rect[3]-rect[1]) * self.height() / self.img.height())
            painter.drawText(rect[0] * self.width() / self.img.width(),
                             rect[1] * self.height() / self.img.height(),
                             str(int(rect[4])))
        if self.start_label:
            rect = self.current_box
            pen = QPen()
            pen.setColor(self.det_color[int(rect[4]) % len(self.det_color)])
            pen.setWidth(self.det_width)
            painter.setPen(pen)
            painter.drawRect(rect[0] * self.width() / self.img.width(),
                             rect[1] * self.height() / self.img.height(),
                             (rect[2] - rect[0]) * self.width() / self.img.width(),
                             (rect[3] - rect[1]) * self.height() / self.img.height())
            painter.drawText(rect[0] * self.width() / self.img.width(),
                             rect[1] * self.height() / self.img.height(),
                             str(int(rect[4])))

    def draw_line(self, painter):
        pen = QPen()
        pen.setColor(self.line_color)
        pen.setWidth(self.line_width)
        painter.setPen(pen)
        painter.drawLine(QPoint(self.current_x, 0), QPoint(self.current_x,5000))
        painter.drawLine(QPoint(0, self.current_y), QPoint(5000,self.current_y))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        self.draw_background(painter)
        self.draw_image(painter)
        self.draw_det_info(painter)
        self.draw_line(painter)

    def mousePressEvent(self, e):
        #正常模式下的操作
        if not self.toggle_fast and not self.toggle_fixup:
            if self.img is None:
                return
            if e.button() == QtCore.Qt.LeftButton:
                # 为什么这里两个坐标的获得方式一样呢？  鼠标按下左键一直不松的事件坐标是什么样的？？？这里只是初始化四个坐标而已，真正有意义的
                # 还是0，1
                self.start_label = True
                self.current_box[0] = e.pos().x() * self.img.width() / self.width()
                self.current_box[1] = e.pos().y() * self.img.height() / self.height()
                self.current_box[2] = e.pos().x() * self.img.width() / self.width()
                self.current_box[3] = e.pos().y() * self.img.height() / self.height()
            if e.button() == QtCore.Qt.RightButton and len(self.box_list) > 0:
                self.box_list.pop()
            self.update()
        
        else:
            # fast模式下 点击鼠标就会将源点框的中心移动到鼠标点击的地方
            if self.toggle_fast:
                if self.img is None:
                    return
                if e.button() == QtCore.Qt.LeftButton:
                    self.start_label = False
                    now_x = e.pos().x() * self.img.width() / self.width()
                    now_y = e.pos().y() * self.img.height() / self.height()
                    diff_x = now_x - self.base_center[0]
                    diff_y = now_y - self.base_center[1]
                    tem = [0,0,0,0,0]
                    for i in self.base_box:
                        tem[0] = i[0] + diff_x
                        tem[1] = i[1] + diff_y
                        tem[2] = i[2] + diff_x
                        tem[3] = i[3] + diff_y
                        tem[4] = i[4]
                        if self.box_list.__len__() == 0:
                            tem[0] = max(tem[0]+random.uniform(-2, 2), 0)
                            tem[1] = max(tem[1]+random.uniform(-5.0, 5.0), 0)
                            tem[2] = min(tem[2]+random.uniform(-1.5, 1.5),self.img.width())
                            tem[3] = min(tem[3]+random.uniform(-3, 3),self.img.height())
                        # 这里要使用深度复制，否则为浅复制（引用）会导致两个框的数值一样
                        self.box_list.append(copy.deepcopy(tem))
                    # if len(self.box_list) < 2:
                    #     pass
                    # else:
                    #     self.box_list[1][0] = self.box_list[1][0] + diff_x
                    #     self.box_list[1][1] = self.box_list[1][1] + diff_y
                    #     self.box_list[1][2] = self.box_list[1][2] + diff_x
                    #     self.box_list[1][3] = self.box_list[1][3] + diff_y
                    
                if e.button() == QtCore.Qt.RightButton and len(self.box_list) > 0:
                    self.box_list = []
                self.update()
                
            # fixup模式下，点击鼠标，会移动base_label的检测框，判断将更靠近鼠标点击处的一角移动到鼠标点击的地方
            elif self.toggle_fixup:
                if self.img is None or self.base_label>=len(self.box_list):
                    return
                if e.button() == QtCore.Qt.LeftButton:
                    self.start_label = False
                    now_x = e.pos().x() * self.img.width() / self.width()
                    now_y = e.pos().y() * self.img.height() / self.height()
                    fix_box = self.box_list[self.base_label]
                    if self.base_label == 1:
                        # base_center = [(self.base_leak_rec[0]+self.base_leak_rec[2])/2, (self.base_leak_rec[1]+self.base_leak_rec[3])/2]
                        # diff_x = now_x - base_center[0]
                        # diff_y = now_y - base_center[1]
                        diff_x = now_x - self.base_leak_rec[0]
                        diff_y = now_y - self.base_leak_rec[1]
                        fix_box[0] = now_x
                        fix_box[1] = now_y
                        fix_box[2] = self.base_leak_rec[2] + diff_x
                        fix_box[3] = self.base_leak_rec[3] + diff_y
                        pass
                    else:    
                        loc_now = now_x + now_y
                        loc_one = fix_box[0]+fix_box[1]
                        loc_tow = fix_box[2]+fix_box[3]
                        if abs(loc_one - loc_now) < abs(loc_tow - loc_now):
                            fix_box[0] = now_x
                            fix_box[1] = now_y
                        else:
                            fix_box[2] = now_x
                            fix_box[3] = now_y
                    self.box_list[self.base_label] = fix_box
                    
                if e.button() == QtCore.Qt.RightButton and len(self.box_list) > 0:
                    del self.box_list[self.base_label]
                
                self.update
                    
                    
                    
                

    def mouseMoveEvent(self, e):
        
        if self.img is None:
            return
        self.current_box[2] = e.pos().x() * self.img.width() / self.width()
        self.current_box[3] = e.pos().y() * self.img.height() / self.height()
        self.current_x = e.pos().x()
        self.current_y = e.pos().y()
        #print(self.current_x, self.current_y, e.button())
        self.update()

    def mouseReleaseEvent(self, e):
        if self.toggle_fast or self.toggle_fixup:
            return
        if self.img is None:
            return
        x1 = e.pos().x()
        y1 = e.pos().y()
        if e.pos().x() >= self.width():
            x1 = self.width()
        if e.pos().x() <= 0:
            x1 = 0
        if e.pos().y() >= self.height():
            y1 = self.height()
        if e.pos().y() <= 0:
            y1 = 0
        x1 = x1 * self.img.width() / self.width()
        y1 = y1 * self.img.height() / self.height()
        if e.button() == QtCore.Qt.LeftButton:
            self.start_label = False
            self.current_box[2] = min(x1, self.img.width())
            self.current_box[3] = min(y1, self.img.height())
            if self.current_box[0] > self.current_box[2]:
                temp_value = self.current_box[2]
                self.current_box[2] = self.current_box[0]
                self.current_box[0] = temp_value
            if self.current_box[1] > self.current_box[3]:
                temp_value = self.current_box[3]
                self.current_box[3] = self.current_box[1]
                self.current_box[1] = temp_value
            if (self.current_box[2]-self.current_box[0])*(self.current_box[3]-self.current_box[1]) >= 1:
                self.box_list.append(copy.deepcopy(self.current_box))
        self.update()

    def leaveEvent(self, e):
        self.current_x = 0
        self.current_y = 0
        self.update()

if __name__ == "__main__":
    cApp = QApplication(sys.argv)
    cImageWidget = CImageWidget()
    cImageWidget.show()
    cImageWidget.set_info('ico.jpg')
    sys.exit(cApp.exec_())