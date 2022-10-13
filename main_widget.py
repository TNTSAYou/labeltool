# -*- coding: utf-8 -*-
from email.mime import base
import sys
import os
from xml.dom.expatbuilder import parseString


if hasattr(sys, 'frozen'):
    os.environ['PATH'] = sys._MEIPASS + ";" + os.environ['PATH']
from PyQt5.QtWidgets import * #QApplication, QWidget, QPushButton, QMainWindow, QVBoxLayout, QHBoxLayout
from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from image_widget import *
import shutil
import glob
from to_coco import COCOCreater
from to_yolov6_v2 import YoloV6Creater 
import multiprocessing
import time
import threading

# ui配置文件
cUi, cBase = uic.loadUiType("main_widget.ui")


def trans_data(main_widget, src_dri, dst_dir, trans_type):
    if trans_type == 'coco':
        coco = COCOCreater(src_dri, dst_dir)
        coco.read_ori_labels()
        main_widget.trans_signal.emit(10)
        coco.create_train_map()
        main_widget.trans_signal.emit(80)
        coco.create_val_map()
        main_widget.trans_signal.emit(100)
    elif trans_type == 'yolov6':
        yolov6_trans = YoloV6Creater(src_dri, dst_dir)
        yolov6_trans.read_ori_labels()
        main_widget.trans_signal.emit(10)
        yolov6_trans.create()
        main_widget.trans_signal.emit(100)
    else:
        print('unsupport type: ', trans_type)
    

# 主界面
class CMainWidget(QWidget, cUi):
    
    # pyqtSignal should be class method
    trans_signal = pyqtSignal(int)
    
    def __init__(self):
        # 设置UI
        QMainWindow.__init__(self)
        cUi.__init__(self)
        self.setupUi(self)
        self.image_dir = ''
        self.label_file = ''
        self.label_info = {}
        self.image_widgets = []
        self.batch_index = 0
        self.side = 2
        self.total = self.side*self.side
        self.trans_process = None
        self.trans_value = 0
        self.trans_dialog = None
        self.trans_signal.connect(self.trans_slot)
        # change to fast model
        self.toggle_fast = False
        # base_box
        self.base_box = '0.jpg'
        self.now_image_name = []
        
        vbox = QVBoxLayout()
        for i in range(self.side):
            hbox = QHBoxLayout()
            for j in range(self.side):
                self.image_widgets.append(CImageWidget())
                hbox.addWidget(self.image_widgets[-1])
            vbox.addLayout(hbox)
        self.frame.setLayout(vbox)
        self.btn_open.clicked.connect(self.slot_btn_open)
        self.btn_save.clicked.connect(self.slot_btn_save)
        self.btn_to_coco.clicked.connect(self.slot_btn_to_coco)
        self.btn_to_voc.clicked.connect(self.slot_btn_to_voc)
        self.btn_to_yolov6.clicked.connect(self.slot_btn_to_yolov6)
        self.btn_back.clicked.connect(self.slot_btn_pre)
        self.btn_next.clicked.connect(self.slot_btn_next)
        self.edit_cls.textChanged.connect(self.slot_edit_change)
        self.btn_to_fast.clicked.connect(self.solt_btn_fast)
        
        
        self.btn_back.hide()
        self.btn_next.hide()

        self.setWindowIcon(QIcon("logo.png"))
        self.setWindowTitle("label tool for detection")
        
        
    def closeEvent(self, event):
        self.save_box_info()
        self.write_label_file()

    def trans_slot(self, trans_vlue):
        print('get signale: ', trans_vlue)
        self.trans_dialog.setValue(trans_vlue)
        if trans_vlue == 100:
            QMessageBox.information(self, u"提示", u"转换结束", QMessageBox.Yes)
            
        
    def read_label_file(self):
        if os.path.exists(self.label_file):
            with open(self.label_file, 'r') as f:
                for line in f:
                    info = line.strip('\r\n')
                    if len(info) == 0:
                        continue
                    domains = info.split(' ')
                    name = domains[0]
                    boxes = []
                    img_path = self.image_dir + '/' + name
                    if not os.path.exists(img_path):
                        print('error:', img_path, 'not exist, ignore it')
                        continue

                    if len(domains) > 1:
                        boxes_str = domains[1:]
                        assert (len(boxes_str) % 5 == 0)
                        box_count = int(len(boxes_str) / 5)
                        for i in range(box_count):
                            box_str = boxes_str[i*5:(i+1)*5]
                            box = [float(x) for x in box_str]
                            boxes.append(box)
                    self.label_info[name] = boxes

    def write_label_file(self):
        if self.label_file == '':
            return 
        with open(self.label_file, 'w') as f:
            for key in self.label_info.keys():
                info = str(key)
                if self.label_info[key] is not None:
                    for box in self.label_info[key]:
                        info += ' %.4f %.4f %.4f %.4f %.4f'%(box[0],box[1],box[2],box[3],box[4])
                f.write(info + '\r')

    def save_box_info(self):
        for image_win in self.image_widgets:
            name, boxes = image_win.get_info()
            if name is not None and len(name) > 0:
                self.label_info[name] = boxes
                
                
    def solt_btn_fast(self):
        self.toggle_fast = not self.toggle_fast
        if self.toggle_fast:
            self.label_model.setText('Fast')
            assert(len(self.label_info[self.base_box]) > 0)
            base_box = self.label_info[self.base_box]
            for i in range(self.total):
                self.image_widgets[i].change_fast(base_box)
        else:
            self.label_model.setText('Normal')
            for i in range(self.total):
                self.image_widgets[i].change_fast(None)
            

    def slot_btn_open(self):
        self.image_dir = QFileDialog.getExistingDirectory(self, u"选择标定图片文件夹", r'D:\YJS\h2o\h2o\3')
        if os.path.exists(self.image_dir):
            self.btn_back.show()
            self.btn_next.show()
            files = os.listdir(self.image_dir)
            for img_name in files:
                if str(img_name).endswith('txt'):
                    continue
                self.label_info[str(img_name)] = None

            self.label_file = self.image_dir + "/label.txt"
            # 按照名称排序
            tem = {}
            # def cmpare(x, y):
            #     x = int(x.split('.')[0])
            #     y = int(y.split('.')[0])
            #     if x>y:
            #         return 1
            #     elif x==y:
            #         return 0
            #     else:
            #         return -1
            for i in sorted(self.label_info, key=lambda x: int(x.split('.')[0])):
                tem[i] = self.label_info[i]
            self.label_info = tem
                
            print("slot_btn_open:", "total images:", len(self.label_info))

            self.read_label_file()
            self.slot_btn_next()

    def update_base_box(self, index):
        self.base_box = self.now_image_name[index]
        assert(len(self.label_info[self.base_box]) > 0)
        base_box = self.label_info[self.base_box]
        for i in range(self.total):
            self.image_widgets[i].change_base_box(base_box)
            
        QMessageBox.information(self, u"提示", u"baseBox变为"+self.now_image_name[index], QMessageBox.Yes)
        

    def keyPressEvent(self, e):
        if(e.key() == Qt.Key_D):
            self.slot_btn_next()
        if(e.key() == Qt.Key_A):
            self.slot_btn_pre()
            
        if(e.key() == Qt.Key_1):
            self.update_base_box(0)
        if(e.key() == Qt.Key_2):
            self.update_base_box(1)
        if(e.key() == Qt.Key_3):
            self.update_base_box(2)
        if(e.key() == Qt.Key_4):
            self.update_base_box(3)
            
        if(e.key() == Qt.Key_S):
            self.slot_btn_save()
            

    def slot_btn_next(self):
        self.save_box_info()
        image_names = self.update_batch_index(next=True, pre=False)
        if image_names is not None:
            for i in range(self.total):
                if i + 1 <= len(image_names):
                    img_path = self.image_dir + '/' + image_names[i]
                    self.image_widgets[i].set_info(img_path, self.label_info[image_names[i]])
                else:
                    self.image_widgets[i].set_info(None, None)

    def slot_btn_pre(self):
        self.save_box_info()
        image_names = self.update_batch_index(next=False, pre=True)
        if image_names is not None:
            for i in range(self.total):
                if i + 1 <= len(image_names):
                    img_path = self.image_dir + '/' + image_names[i]
                    self.image_widgets[i].set_info(img_path, self.label_info[image_names[i]])
                else:
                    self.image_widgets[i].set_info(None, None)

    def slot_btn_to_coco(self):
        print('to coco')
        self.slot_btn_save()
        if self.trans_process is not None and self.trans_process.is_alive():            
            QMessageBox.critical(self, u"提示", u"正在转换数据集，请稍后", QMessageBox.Yes)
            return
            
        save_dir = QFileDialog.getExistingDirectory(self, u"选择COCO保存文件夹", os.getcwd())
        if os.path.exists(save_dir):
            if os.listdir(save_dir):
                ret = QMessageBox.critical(self, u"警告", u"所选文件夹(%s)非空，继续转换将会清空该文件夹"%save_dir, QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.Yes:
                    shutil.rmtree(save_dir)
                    os.mkdir(save_dir)
                else:
                    return
                   
            self.trans_process = threading.Thread(target=trans_data, args = (self, self.image_dir, save_dir, 'coco',))
            self.trans_process.start()
            
            self.trans_dialog = QProgressDialog(self)
            self.trans_dialog.setWindowTitle("转换中")  
            self.trans_dialog.setLabelText("正在转换，请勿关闭...")
            self.trans_dialog.setMinimumDuration(1)
            self.trans_dialog.setWindowModality(Qt.WindowModal)
            self.trans_dialog.setRange(1,100) 
            self.trans_dialog.setValue(1)
            self.trans_dialog.show()
            
    def slot_btn_to_yolov6(self):
        print('to yolov6')
        self.slot_btn_save()
        if self.trans_process is not None and self.trans_process.is_alive():            
            QMessageBox.critical(self, u"提示", u"正在转换数据集，请稍后", QMessageBox.Yes)
            return
            
        save_dir = QFileDialog.getExistingDirectory(self, u"选择YoloV6格式数据保存文件夹", os.getcwd())
        if os.path.exists(save_dir):
            if os.listdir(save_dir):
                ret = QMessageBox.critical(self, u"警告", u"所选文件夹(%s)非空，继续转换将会清空该文件夹"%save_dir, QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.Yes:
                    shutil.rmtree(save_dir)
                    os.mkdir(save_dir)
                else:
                    return
                   
            self.trans_process = threading.Thread(target=trans_data, args = (self, self.image_dir, save_dir, 'yolov6',))
            self.trans_process.start()
            
            self.trans_dialog = QProgressDialog(self)
            self.trans_dialog.setWindowTitle("转换中")  
            self.trans_dialog.setLabelText("正在转换，请勿关闭...")
            self.trans_dialog.setMinimumDuration(1)
            self.trans_dialog.setWindowModality(Qt.WindowModal)
            self.trans_dialog.setRange(1,100) 
            self.trans_dialog.setValue(1)
            self.trans_dialog.show()
            
    def slot_btn_to_voc(self):
        print('to voc')
        self.slot_btn_save()
        QMessageBox.critical(self, u"提示", u"VOC数据集转换正在开发中...", QMessageBox.Yes)

    def slot_edit_change(self):
        try:
            a = int(self.edit_cls.text())
            for image_win in self.image_widgets:
                image_win.set_current_cls(a)
        except:
            return

    def slot_btn_save(self):
        self.save_box_info()
        self.write_label_file()
        QMessageBox.critical(self, u"提示", u"已保存", QMessageBox.Yes)

        
    def update_batch_index(self, next=True, pre=False):
        if len(self.label_info.keys()) == 0:
            return None
        assert (next != pre)
        self.total_batch = math.ceil(len(self.label_info.keys()) / self.total)
        if next:
            if self.batch_index == self.total_batch:
                return None
            if self.batch_index == self.total_batch - 1:
                last_batch_count = len(self.label_info.keys()) % self.total
                if last_batch_count == 0:
                    last_batch_count = self.total
                image_names = list(self.label_info.keys())[self.batch_index * self.total: self.batch_index * self.total + last_batch_count]
                self.batch_index += 1
            if self.batch_index < self.total_batch - 1:
                batch_count = self.total
                image_names = list(self.label_info.keys())[self.batch_index * self.total: self.batch_index * self.total + batch_count]
                self.batch_index += 1
        else:
            if self.batch_index == 1:
                return None
            else:
                self.batch_index -= 1
                image_names = list(self.label_info.keys())[(self.batch_index-1) * self.total: (self.batch_index-1) * self.total + self.total]

        self.label_jindu.setText('%d/%d'%(self.batch_index, self.total_batch))
        self.now_image_name = image_names
        return image_names

        

if __name__ == "__main__":
    cApp = QApplication(sys.argv)
    cMainWidget = CMainWidget()
    cMainWidget.show()
    sys.exit(cApp.exec_())