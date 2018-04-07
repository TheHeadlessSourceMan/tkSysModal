#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
This allows you to create a windows system-modal dialog using tkinter
(For instance, like the UAC dialog)

SysmodalMessageBox is a simple message box if all you want to do is ask a question

SysmodalDialog is more advanced.  It lets you send in any Tkinter Frame class and parameters
and will create the the window for you in sysmodal mode.
"""

import sys
import time
#import tkinter
import Tkinter as tkinter
import threading
import time
from PIL import ImageGrab,ImageEnhance

import winerror
import win32con
import win32api
import win32service

from Tkinter import Frame, Tk, Label, Toplevel
import tkMessageBox
from PIL import Image, ImageTk, ImageFilter

class SysmodalBase(Frame):
	"""
	This is a base class.  Do not use directly!
	"""
	
	def __init__(self,master,backgroundImg=None,safetyTimeout=None):
		"""
		safetyTimeout - in milliseconds, can keep you from
			getting stuck in limbo when debugging
		"""
		self.safetyTimeout=safetyTimeout
		if backgroundImg==None:
			backgroundImg=ImageGrab.grab()
		self.backgroundImg=backgroundImg
		Frame.__init__(self,master)
		master.overrideredirect(True)
		#master.attributes("-fullscreen",True)
		master.borderwidth=0
		w=master.winfo_screenwidth()
		h=master.winfo_screenheight()
		master.geometry('%dx%d+%d+%d' % (w, h, 0, 0))
		self.pack()
		self.createBackground()
		# safety net whilest debugging
		if safetyTimeout!=None:
			self.master.after(safetyTimeout,self.master.destroy)

	def createBackground(self):
		# background window is a faded copy of the desktop
		enhancer=ImageEnhance.Contrast(self.backgroundImg)
		self.backgroundImg=enhancer.enhance(0.8)
		enhancer=ImageEnhance.Sharpness(self.backgroundImg)
		self.backgroundImg=enhancer.enhance(0.0)
		enhancer=ImageEnhance.Brightness(self.backgroundImg)
		self.backgroundImg=enhancer.enhance(0.8)
		self.photo1=ImageTk.PhotoImage(self.backgroundImg.convert("RGB"))
		self.label1=Label(self,image=self.photo1)
		self.label1.grid(row=0, column=0)
		
	@staticmethod
	def _setDesktopWallpaper(filename):
		"""
		for more, see:
			https://msdn.microsoft.com/en-us/library/ms724947(VS.85).aspx
			http://stackoverflow.com/questions/1977694/how-can-i-change-my-desktop-background-with-python
		"""
		import ctypes
		SPI_SETDESKWALLPAPER=20 
		ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER,0,filename,0)
	@staticmethod		
	def _getDesktopWallpaper():
		"""
		for more, see:
			https://msdn.microsoft.com/en-us/library/ms724947(VS.85).aspx
			http://stackoverflow.com/questions/1977694/how-can-i-change-my-desktop-background-with-python
		"""
		import ctypes
		SPI_GETDESKWALLPAPER=0x0073
		return ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER,0,None,0)
	
	@staticmethod
	def _playUACSound():
		path=r'C:\Windows\Media\Windows User Account Control.wav'
		import winsound
		winsound.PlaySound(path,winsound.SND_FILENAME)
		
	@staticmethod
	def _closeDesktop(hDesk,numtries=10):
		"""
		call hDesk.CloseDesktop() but in a way that gives us maximum chance of succeeding
		"""
		for i in range(numtries):
			try:
				return hDesk.CloseDesktop()
			except win32service.error as e:
				if e.winerror!=winerror.ERROR_BUSY or i==numtries-1:
					raise
				# otherwise, keep trying
			time.sleep(0.1)
			

class SysmodalMessageBox(SysmodalBase):
	def __init__(self,master,title,message,mbType,resultObj,backgroundImg=None,safetyTimeout=None):
		"""
		mbType can be:
			okcancel
			yesno
			error
			info
			warning
			question
		"""
		self.title=title
		self.message=message
		self.resultObj=resultObj
		SysmodalBase.__init__(self,master,backgroundImg,safetyTimeout)
		self.resultObj.result=tkMessageBox.askokcancel(self.title,self.message)
		self.master.destroy()

	@classmethod
	def _dialogThread(clazz,hDesk,title,message,mbType,resultObj,backgroundImg=None,safetyTimeout=None):
		# keep a link to the current desktop so we can get back
		hDeskInputOld=win32service.OpenInputDesktop(0,False,win32con.DESKTOP_SWITCHDESKTOP)
		try:
			# set the ui desktop of this thread to the new desktop
			# so that our windows go to the right place!
			hDesk.SetThreadDesktop()
			# visually switch to the new desktop
			hDesk.SwitchDesktop()
			try:
				# run the TK dialog
				root=tkinter.Tk()
				app=SysmodalMessageBox(root,title,message,mbType,resultObj,backgroundImg,safetyTimeout)
				app.mainloop()
			finally:
				# switch back to the original desktop
				hDeskInputOld.SwitchDesktop()
		finally:
			# be a good citizen and release our link to the current desktop
			SysmodalBase._closeDesktop(hDeskInputOld)
		
	@classmethod
	def run(clazz,title='',message='',mbType=None,safetyTimeout=None):
		"""
		returns True/False depending on the result of the message box
		"""
		# get a screenshot of the current desktop (new desktop background will be based on this)
		backgroundImg=ImageGrab.grab()
		# create a new desktop
		hDesk=win32service.CreateDesktop("SysModalDesktop",0,win32con.GENERIC_ALL,None)
		# use a dummy object to pass the result back from the thread
		class Result:
			pass
		resultObj=Result()
		# need to run dialog in its own thread, which is associated with the new desktop
		try:
			thread=threading.Thread(target=clazz._dialogThread,args=(hDesk,title,message,mbType,resultObj,backgroundImg,safetyTimeout))
			thread.start()
			thread.join()
		finally:
			# delete the new desktop
			clazz._closeDesktop(hDesk)
		# extract the result from the dummy object
		if hasattr(resultObj,'result'):
			return resultObj.result
		return None
		
		
class SysmodalDialog(SysmodalBase):
	def __init__(self,master,resultObj,backgroundImg,safetyTimeout,frameClass,*frameClassParams,**frameClassNamedParams):
		SysmodalBase.__init__(self,master,backgroundImg,safetyTimeout)
		childWindow=Toplevel(self)
		childWindow.attributes("-topmost",True)
		resultObj.result=frameClass(childWindow,*frameClassParams,**frameClassNamedParams)
		sw=master.winfo_screenwidth()
		sh=master.winfo_screenheight()
		childWindow.update()
		w=childWindow.winfo_reqwidth()
		h=childWindow.winfo_reqheight()
		childWindow.geometry('%dx%d+%d+%d' % (w,h,sw/2-w/2,sh/2-h/2))
		self._playUACSound()
		
	@classmethod
	def _dialogThread(clazz,hDesk,resultObj,backgroundImg,safetyTimeout,frameClass,*frameClassParams,**frameClassNamedParams):
		# keep a link to the current desktop so we can get back
		hDeskInputOld=win32service.OpenInputDesktop(0,False,win32con.DESKTOP_SWITCHDESKTOP)
		oldWallpaper=clazz._getDesktopWallpaper()
		try:
			# set the ui desktop of this thread to the new desktop
			# so that our windows go to the right place!
			hDesk.SetThreadDesktop()
			clazz._setDesktopWallpaper('') # make sure the background is black
			# visually switch to the new desktop
			hDesk.SwitchDesktop()
			try:
				# run the TK dialog
				root=tkinter.Tk()
				app=SysmodalDialog(root,resultObj,backgroundImg,safetyTimeout,frameClass,*frameClassParams,**frameClassNamedParams)
				app.mainloop()
			finally:
				# switch back to the original desktop
				hDeskInputOld.SwitchDesktop()
		finally:
			clazz._setDesktopWallpaper(oldWallpaper)
			# be a good citizen and release our link to the current desktop
			SysmodalBase._closeDesktop(hDeskInputOld)
		
	@classmethod
	def run(clazz,safetyTimeout,frameClass,*frameClassParams,**frameClassNamedParams):
		"""
		Returns the instanciated frameClass that was run.
		(Useful for getting form values)
		"""
		# get a screenshot of the current desktop (new desktop background will be based on this)
		backgroundImg=ImageGrab.grab()
		# create a new desktop
		hDesk=win32service.CreateDesktop("SysModalDesktop",0,win32con.GENERIC_ALL,None)
		# use a dummy object to pass the result back from the thread
		class Result:
			pass
		resultObj=Result()
		# need to run dialog in its own thread, which is associated with the new desktop
		try:
			args=[hDesk,resultObj,backgroundImg,safetyTimeout,frameClass]
			args.extend(frameClassParams)
			thread=threading.Thread(target=clazz._dialogThread,args=args,kwargs=frameClassNamedParams)
			thread.start()
			thread.join()
		finally:
			# delete the new desktop
			clazz._closeDesktop(hDesk)
		# extract the result from the dummy object
		if hasattr(resultObj,'result'):
			return resultObj.result
		return None

if __name__ == '__main__':
	result=SysmodalMessageBox.run('Question','Are you sure?','yesno',5000)
	print result
	sys.exit(result)