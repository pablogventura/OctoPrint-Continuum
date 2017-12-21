# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.util import RepeatedTimer
import time
import os

# self._data_folder datos del plugin
# self._file_manager.path_on_disk("local",u'20mm_hollow_cube.gcode') devuele el directorio
# self._file_manager.remove_file(path)

class DisplayETAPlugin(octoprint.plugin.ProgressPlugin,
                       octoprint.plugin.TemplatePlugin,
                       octoprint.plugin.AssetPlugin,
                       octoprint.plugin.EventHandlerPlugin,
                       octoprint.plugin.StartupPlugin):

    def __init__(self):
        self.timer = RepeatedTimer(5.0, DisplayETAPlugin.fromTimer, args=[self], run_first=True,)



    def reverse_readlines(self, filename, stop, buf_size=8192):
        """a generator that returns the lines of a file in reverse order"""
        with open(filename) as fh:
            segment = None
            offset = stop
            fh.seek(stop)
            file_size = remaining_size = fh.tell()
            while remaining_size > 0:
                offset = min(file_size, offset + buf_size)
                fh.seek(file_size - offset)
                buffer = fh.read(min(remaining_size, buf_size))
                remaining_size -= buf_size
                lines = buffer.split('\n')
                # the first line of the buffer is probably not a complete line so
                # we'll save it and append it to the last line of the next buffer
                # we read
                if segment is not None:
                    # if the previous chunk starts right from the beginning of line
                    # do not concact the segment to the last line of new chunk
                    # instead, yield the segment first 
                    if buffer[-1] is not '\n':
                        lines[-1] += segment
                    else:
                        yield segment
                segment = lines[0]
                for index in range(len(lines) - 1, 0, -1):
                    if len(lines[index]):
                        yield lines[index]
            # Don't yield None if the file was empty
            if segment is not None:
                yield segment
	def get_settings_defaults(self):
		return dict(
			defaultFanSpeed=100,
			minSpeed=0,
			maxSpeed=100,
			notifyDelay=4000
            )
    def on_after_startup(self):
    
        s.setInt(["notifyDelay"], data["notifyDelay"])
        self.get_settings_updates()
        #clean up settings if everything's default
        self._logger.info(self._settings.getInt(["notifyDelay"]))
		if "notifyDelay" in data.keys():
			s.setInt(["notifyDelay"], data["hola"])
		self.get_settings_updates()
		#clean up settings if everything's default
		self.on_settings_cleanup()
        s.save()
        #self._logger.info(self._file_manager.list_files())
        #import ipdb
        #ipdb.set_trace()
        #self._logger.info(self._storage("local").path_on_disk("20mm_hollow_cube.gcode"))
        
        #return
        if os.path.isfile(os.path.join(self._data_folder,"print_recovery")):
            #hay que recuperar
            self._logger.info("Hubo un corte de luz la ultima vez")
            f = open(os.path.join(self._data_folder,"print_recovery"), 'r')
            filename,filepos,currentZ,bedT,tool0T=f.readline().split()
            self._logger.info("y fue asi %s por %s en Z:%s a Bed:%s Tool:%s"%(filename,filepos,currentZ, bedT, tool0T))
            recovery_fn = self.generateContinuation(filename,filepos,currentZ, bedT, tool0T)
            self._printer.select_file(recovery_fn, False, printAfterSelect=True) # larga imprimiendo directamente
        else:
            self._logger.info("No Hubo un corte de luz la ultima vez")
    
    def generateContinuation(self,filename,filepos,currentZ, bedT, tool0T):
        try:
            filepos = int(filepos)
        except:
            #no habia llegado a empezar
            return
        gcode = "M80\n"
        gcode += "M140 S%s\n" % bedT
        gcode += "M104 S%s\n" % tool0T
        gcode += "M190 S%s\n" % bedT
        gcode += "M109 S%s\n" % tool0T
        gcode += "G21 ;metric values\n"
        gcode += "G90 ;absolute positioning\n"
        gcode += "G28 X0 Y0 ;move X/Y to min endstops\n"
        gcode += "G92 E0 Z%s ;zero the extruded length again\n" % (float(currentZ)+2) # le sumo Z_HOMING_HEIGHT
        gcode += "M211 S0\n" #desactivo los software endstops TODO desactivarlos solo para saldar el Z_HOMING_HEIGHT        
        gcode += "G91\n"
        gcode += "G1 Z-%s F200 ; correcting Z_HOMING_HEIGHT\n" % (2) # Z_HOMING_HEIGHT
        gcode += "G90\n"
        gcode += "M211 S1\n" #reactivo los software endstops TODO desactivarlos solo para saldar el Z_HOMING_HEIGHT
        gcode += "G1 F9000\n"
        
        original_fn = self._file_manager.path_on_disk("local",filename)
        recovery_fn=self._file_manager.path_on_disk("local","recovery_" + filename)
        
        fan=False
        extruder=False
        for line in self.reverse_readlines(original_fn, filepos):
            # buscando las ultimas lineas importantes
            if not fan and (line.startswith("M106") or line.startswith("M107")):
                fan = True # encontre el fan
                gcode += line +"\n"
            if not extruder and (line.startswith("G1 ") or line.startswith("G92 ")) and ("E" in line):
                # G1 X135.248 Y122.666 E4.03755
                extruder = True # encontre el extruder
                subcommands = line.split() # dividido por espacios
                ecommand = [sc for sc in subcommands if "E" in sc]
                assert len(ecommand)==1
                ecommand = ecommand[0]
                gcode += "G92 " + ecommand +"\n"
            if fan and extruder:
                break
        
        original = open(original_fn, 'r')
        recovery = open(recovery_fn, 'w')
        
        recovery.write(gcode)
        original.seek(filepos)
        recovery.write(original.read())
        recovery.write("\nM211 S1\n")# reactivo los software endstops
        original.close()
        recovery.close()
        return recovery_fn
        
    def fromTimer(self):
        #self.eta_string = self.calculate_ETA()
        #self._plugin_manager.send_plugin_message(self._identifier, dict(eta_string=self.eta_string))
        currentData = self._printer. get_current_data()
        currentTemp = self._printer.get_current_temperatures()
        self._logger.info(currentTemp)
        bedT=currentTemp["bed"]["target"]
        tool0T=currentTemp["tool0"]["target"]
        filepos=currentData["progress"]["filepos"]
        filename=currentData["job"]["file"]["name"]
        currentZ=currentData["currentZ"]
        self._logger.info("imprimiendo %s por %s en Z:%s a Bed:%s Tool:%s"%(filename,filepos,currentZ, bedT, tool0T))
        f = open(os.path.join(self._data_folder,"print_recovery"), 'w')
        f.write("%s %s %s %s %s"%(filename,filepos,currentZ, bedT, tool0T))
        f.close()
        self._logger.info("Escrito")

    def clean(self):
        try:
            os.remove(os.path.join(self._data_folder,"print_recovery"))
        except:
            pass
            
    def on_event(self,event, payload):
        if event.startswith("Print"):
            if event in {"PrintStarted"}: # empiezo a revisar
                # empiezo a chequear
                self.timer = RepeatedTimer(5.0, DisplayETAPlugin.fromTimer, args=[self], run_first=True,)
                self.timer.start()
            elif event in {"PrintDone","PrintFailed","PrintCancelled"}: # casos en que dejo de revisar y borro
                # cancelo el chequeo
                self.timer.cancel()
                self.clean()
            else:
                # casos pause y resume
                pass 
                
            

__plugin_name__ = "Display ETA"
__plugin_identifier = "display-eta"
__plugin_version__ = "1.0.0"
__plugin_description__ = "A quick \"Hello World\" example plugin for OctoPrint"
__plugin_implementation__ = DisplayETAPlugin()
