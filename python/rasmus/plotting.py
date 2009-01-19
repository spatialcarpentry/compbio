"""
 file: plotting.py 
 authors: Matt Rasmussen
 date: 11/30/05

 Plotting classes and functions: R plotting, GNUPLOT wrapper, svg, heatmaps
"""

from rasmus.util import *
from rasmus import svg

import sys, os
import tempfile as temporaryfile


#=============================================================================
# R plotting

# private global rplot state
_rplot_pdf = None
_rplot_temp = False
_rplot_viewer = "xpdf"


class LazyR (object):
    """Allows lazy loading of rpy"""

    def __init__(self, name):
        self.__name = name

    def __getattr__(self, attr):        
        import rpy
        globals()[self.__name] = rpy.r
        return rpy.r.__getattr__(attr)

    def __call__(self, *args, **kargs):
        import rpy
        globals()[self.__name] = rpy.r
        return rpy.r(*args, **kargs)

rp = LazyR("rp")


def rplot_start(filename, *args, **kargs):
    """Starts a new PDF file"""
    
    global _rplot_pdf
    rp.pdf(file=filename, *args, **kargs)
    _rplot_pdf = filename

def rplot_end(show=False):
    """Ends a PDF file"""
    
    global _rplot_pdf, _rplot_temp
    rp.dev_off()
    
    if show:
        if _rplot_temp:
            os.system("('%s' '%s'; rm '%s') &" % 
                      (_rplot_viewer, _rplot_pdf, _rplot_pdf))
        else:
            os.system("('%s' '%s') &" % (_rplot_viewer, _rplot_pdf))

    _rplot_pdf = None
    _rplot_temp = False


def rplot(func, *args, **kargs):
    """Wrapper for plotting with R.

       Makes sensible plot labels and manages pdf plotting"""
    
    global _rplot_pdf, _rplot_temp
    
    kargs.setdefault("xlab", "")
    kargs.setdefault("ylab", "")
    kargs.setdefault("main", "")
    
    # parse my args
    if "pdf" in kargs:
        _rplot_pdf = kargs["pdf"]
        _rplot_temp = True  
        del kargs["pdf"]
        rp.pdf(file=_rplot_pdf)
        self_open = True
    else:
        self_open = False


    if "show" in kargs:
        show = kargs["show"]
        del kargs["show"]
    else:
        show = False           

    # prepare tempfile if needed
    if _rplot_pdf is None:
        f, _rplot_pdf = temporaryfile.mkstemp(".pdf", "rplot_")
        _rplot_temp = True
        os.close(f)        
        rp.pdf(file=_rplot_pdf)
        
        # force show for tempfile
        self_open = True
        show = True
            
    
    if "pdf_close" in kargs:
        close = kargs["pdf_close"]
        del kargs["pdf_close"]
    else:
        if self_open:
            close = True
        else:
            close = False
    
    
    # make R call   
    rp.__getattr__(func)(*args, **kargs)
    
    # close PDF and show
    if close:
        if _rplot_pdf is not None:
            rplot_end(show)


def rplotfunc(self, cmd, func, start, end, step, **options):
    """Plots a function using R"""
    x = []
    y = []
    
    while start < end:
        try:
            y.append(func(start))
            x.append(start)
        except ZeroDivisionError:
            pass
            start += step
    rplot(cmd, x, y, **options)
    

def rhist(*args, **kargs):
    """Plots a histogram"""
    rplot("hist", *args, **kargs)

def rplot_set_viewer(viewer):
    global _rplot_viewer
    _rplot_viewer = viewer

def rplot_get_viewer(viewer):
    return _rplot_viewer


#=============================================================================
# Color maps


# common colors
red    = ( 1,  0,  0,  1)
orange = ( 1, .5,  0,  1)
yellow = ( 1,  1,  0,  1)
green  = ( 0,  1,  0,  1)
blue   = ( 0,  0,  1,  1)
purple = ( 1,  0,  1,  1)
black  = ( 0,  0,  0,  1)
grey   = (.5, .5, .5,  1)
white  = ( 1,  1,  1,  1)


class ColorMap:
    """ColorMap maps values on the real line to colors"""
    
    
    def __init__(self, table=[]):
        """
        'table' should be the following format:
        
        [
          [val1, color1],
          [val2, color2],
          [val3, color3],
          ...etc..
        ]
        
        Values bewteen val1 and val2 will be assigned a blend of 
        color1 and color2.  value-color pairs can be specified in any order 
        within table.
        
        """
        self.table = table
        
        self.table.sort(key=lambda x: x[0])
    
    
    def get(self, value):
        """Returns values in [0, 1]"""
    
        # determine where color falls in table
        for i in xrange(len(self.table)):
            if value <= self.table[i][0]:
                break
        if i > 0:
            i -= 1
        
        
        if value <= self.table[i][0]:
            # return lower bound color
            return self.table[i][1]
        elif value >= self.table[i+1][0]:
            # return upper bound color
            return self.table[i+1][1]
        else:
            # blend two nearest colors
            part = value - self.table[i][0]
            tot = float(self.table[i+1][0] - self.table[i][0])
            weight1 = (tot-part)/tot
            weight2 = part/tot
            
            newcolor = []
            color1 = self.table[i][1]
            color2 = self.table[i+1][1]
            for j in range(len(color1)):
                newcolor.append(weight1 * color1[j] + 
                                weight2 * color2[j])
            
            return newcolor
    
    
    def getInt(self, value):
        return [int(x*255) for x in self.get(value)]
    

def get_webcolor(color, maxval=1):
    
    colstr = "#"
    for i in color:
        h = hex(int(i * 255.0 / maxval))[2:]
        if len(h) == 1:
            h = "0" + h
        colstr += h
    return colstr


def rainbowColorMap(data=None, low=None, high=None):
    if data != None:
        low = min(data)
        high = max(data)
    assert low != None and high != None
    
    return ColorMap([[low, blue],
                     [.5*low+.5*high, green],
                     [.25*low + .75*high, yellow],
                     [high, red]])
   


#=============================================================================
# svg plotting
    
def plothist2(x, y, ndivs1=20, ndivs2=20, width=500, height=500):
    l, h = hist2(x, y, ndivs1, ndivs2)
    bwidth = bucketSize(x)
    bheight = bucketSize(y)
    
    #width *= bwidth/bheight
    
    heatmap(h, width/ndivs1, height/ndivs2)



def makeColorLegend(filename, colormap, start, end, step, 
                    width=100, height=10):
    s = svg.Svg(openStream(filename, "w"))    
    s.beginSvg(width, height)
    
    xscale =  float(width) / (end + step - start)
    
    for i in frange(start, end + step, step):
        color = colormap.get(i)
        s.rect((i-start) * xscale, 
               0, 
               step*xscale, height, 
               color, color)
    
    s.endSvg()
    
    
    


def heatmap(matrix, width=20, height=20, colormap=None, filename=None,
            rlabels=None, clabels=None, display=True, 
            xdir=1, ydir=1, 
            xmargin=0, ymargin=0,
            labelPadding=2,
            labelSpacing=4,
            showVals=False,
            valColor=black):
    
    
    
    # determine filename
    if filename == None:
        filename = tempfile(".", "heatmap", ".svg")
        temp = True
    else:
        temp = False
    
    # determine colormap
    if colormap == None:
        colormap = rainbowColorMap(flatten(matrix))
    
    # determine matrix size and orientation
    nrows = len(matrix)
    ncols = len(matrix[0])
    
    if xdir == 1:
        xstart = xmargin
        ranchor = "end"
        coffset = width
    elif xdir == -1:
        xstart = xmargin + ncols * width
        ranchor = "start"
        coffset = 0
    else:
        raise Exception("xdir must be 1 or -1")
            
    if ydir == 1:
        ystart = ymargin
        roffset = height
        canchor = "start"
    elif ydir == -1:
        ystart = ymargin + nrows * width
        roffset = 0
        canchor = "end"
    else:
        raise Exception("ydir must be 1 or -1")
    
    
    # begin svg
    infile = openStream(filename, "w")
    s = svg.Svg(infile)
    s.beginSvg(ncols*width + 2*xmargin, nrows*height + 2*ymargin)
    
    # draw matrix
    for i in xrange(nrows):
        for j in xrange(ncols):
            color = colormap.get(matrix[i][j])
            s.rect(xstart + xdir*j*width, 
                   ystart + ydir*i*height, 
                   xdir*width, ydir*height, color, color)
    
    # draw values
    if showVals:
        # find text size
        
        fontwidth = 7/11.0
        
        textsize = []
        for i in xrange(nrows):
            for j in xrange(ncols):
                strval = "%.2f" % matrix[i][j]
                textsize.append(min(height, width/(float(len(strval)) * fontwidth)))
        textsize = min(textsize)
    
        for i in xrange(nrows):
            for j in xrange(ncols):
                strval = "%.2f" % matrix[i][j]
                s.text(strval, 
                       xstart + xdir*j*width, 
                       ystart + ydir*i*height + 
                       height/2.0 + textsize/2.0, 
                       textsize,
                       fillColor=valColor)
    
    # draw labels
    if rlabels != None:
        assert len(rlabels) == nrows, \
            "number of row labels does not equal number of rows"
        
        for i in xrange(nrows):
            x = xstart - xdir*labelPadding
            y = ystart + roffset + ydir*i*height - labelSpacing/2.
            s.text(rlabels[i], x, y, height-labelSpacing, anchor=ranchor)
    
    if clabels != None:
        assert len(clabels) == ncols, \
            "number of col labels does not equal number of cols"
        
        for j in xrange(ncols):
            x = xstart + coffset + xdir*j*width - labelSpacing/2.
            y = ystart - ydir*labelPadding
            s.text(clabels[j], x, y, width-labelSpacing, anchor=canchor, angle=270)
    
    # end svg
    s.endSvg()
    s.close()
    
    
    # display matrix
    if display:
        os.system("display %s" % filename)
    
    # clean up temp files
    if temp:
        os.remove(filename)




#=============================================================================
# Gnuplot


class Gnuplot:
    class Plot:
        def __init__(self, xlist, ylist, zlist, options):
            self.xlist = copy.copy(xlist)
            self.ylist = copy.copy(ylist)
            self.zlist = copy.copy(zlist)
            self.options = copy.copy(options)

    def __init__(self):
        self.data = []
        self.stream = None
        
        self.margin = .1
        self.enable = True

        self.options = {
            # plot options
            "style" : "points",
            "main"  : "",
            "xlab"  : "",
            "ylab"  : "",
            "zlab"  : "",
            "plab"  : "",
            "eqn": None,
            
            # graph options
            "xmin" : None,
            "xmax" : None,
            "ymin" : None,
            "ymax" : None,
            "zmax" : None,
            "zmin" : None,
            "xtics" : None,
            "ytics" : None,
            "ztics" : None,
            "xlog": None,
            "ylog": None,
            "zlog": None,
            "margin": None
            }
        
        self.DATA_ONLY_OPTION = ["err", "errlow", "errhi"]
        
    
    def set(self, **options):
        if "noreplot" in options:
            noreplot = False
            del option["noreplot"]
        else:
            noreplot = True
        
        for key in options:
            if key in self.DATA_ONLY_OPTION:
                continue
            self.options[key] = options[key]
        
        if not noreplot:
            self.replot()
    
    def gnuplot(self, text):
        self.stream.write(text)
    
    def xrange(self, start = None, end = None):
        self.options["xmin"] = start
        self.options["xmax"] = end
        self.replot()
    
    def yrange(self, start = None, end = None):
        self.options["ymin"] = start
        self.options["ymax"] = end
        self.replot()
    
    def zrange(self, start = None, end = None):
        self.options["zmin"] = start
        self.options["zmax"] = end
        self.replot()
    
    def unlog(self):
        self.options["xlog"] = False
        self.options["ylog"] = False
        self.options["zlog"] = False
        self.replot()
    
    def xlog(self, base=10):
        self.options["xlog"] = base
        self.replot()
    
    def ylog(self, base=10):
        self.options["ylog"] = base
        self.replot()
        
    def zlog(self, base=10):
        self.options["zlog"] = base
        self.replot()
    
    def loglog(self, base=10):
        self.options["xlog"] = base
        self.options["ylog"] = base
        self.replot()

    def clear(self):
        self.data = []       
    
        
    def save(self, filename = "", format="x11"):
        if not self.enable:
            return
    
        
        
        if filename == "":
            tmpfile = self.setTerminal(filename, format)
        
            self.replot()
            
            # wait until plot appears
            self.wait()
            
            text = file(tmpfile).read()
            os.remove(tmpfile)
        else:
            self.setTerminal(filename, format)
        
            self.replot()
            text = None
            
        # reset format
        print >>self.stream, "set terminal x11"
        
        return text        
    
    
    def savedata(self, filename):
        """Save gnuplot commands in filename"""
        
        self.stream = file(filename, "w")
        self.replot()
        self.enableOutput()

    def savetab(self, filename):
        """Save data in tab delimited format"""
        
        out = openStream(filename, "w")

        for data in self.data:
            print >>out, data.options["plab"]

            if len(data.ylist) > 0:
                if len(data.zlist) > 0:
                    rows = zip(data.xlist, data.ylist, data.zlist)
                    labels = [data.options[i]
                              for i in ["xlab", "ylab", "zlab"]]
                else:
                    rows = zip(data.xlist, data.ylist)
                    labels = [data.options[i]
                              for i in["xlab", "ylab"]]

            print >>out, "\t".join(labels)
            for row in rows:
                print >>out, "\t".join(map(str, row))
            print >>out    
    
    
    def saveall(self, filename):
        """
        Save gnuplot commands, tad delimited, and plot image in the 
        following files:
            
            <filename>.ps
            <filename>.tab
            <filename>.png
        
        """
        
        if not self.enable:
            return
        
        
        self.savetab(filename + ".tab")
        self.save(filename + ".png")
        self.save(filename + ".ps")        
        
        
    
    def setTerminal(self, filename = "", format="x11"):
        if not self.enable:
            return
        
        # auto detect format from filename
        if filename != "":
            print >>self.stream, "set output \"%s\"" % filename
        
            # determine format
            if filename.endswith(".ps"):
                format = "ps"
            if filename.endswith(".pdf"):
                format = "pdf"
            if filename.endswith(".gif"):
                format = "gif"
            if filename.endswith(".png"):
                format = "png"
            if filename.endswith(".jpg"):
                format = "jpg"
        else:
            tmpfile = tempfile(".", "gnuplot", ".ps")
            print >>self.stream, "set output \"%s\"" % tmpfile
            return tmpfile
        
        
        # set terminal format
        if format == "ps":
            print >>self.stream, "set terminal postscript color"
        elif format == "pdf":
            print >>self.stream, "set terminal pdf"
        elif format == "gif":
            print >>self.stream, "set terminal gif"
        elif format == "jpg":
            print >>self.stream, "set terminal jpeg"
        else:
            print >>self.stream, "set terminal %s" % format
    
    
    
    def wait(self):
        """Wait until all commands are known to be excuted"""
        
        tmpfile = tempfile(".", "gnuplot", ".ps")
        print >>self.stream, "set output '%s'" % tmpfile
        print >>self.stream, "set terminal postscript color"
        print >>self.stream, "plot '-'\n0 0\ne\n"
        self.stream.flush()
        
        while not os.path.isfile(tmpfile): pass
        os.remove(tmpfile)
        
    
    def findRange(self):
        bestLeft = INF
        bestRight = -INF
        bestTop = -INF
        bestBottom = INF
    
        # find ranges for each graph that is plotted
        for graph in self.data:
            if graph.options["eqn"]:
                continue
            
            list1 = graph.xlist
            list2 = graph.ylist

            # find border
            top    = max(list2)
            bottom = min(list2)
            left   = min(list1)
            right  = max(list1)
            
            # record biggest range thus far
            if top > bestTop:       bestTop = top
            if bottom < bestBottom: bestBottom = bottom
            if left < bestLeft:     bestLeft = left
            if right > bestRight:   bestRight = right
        
        # find margin
        ymargin = (bestTop - bestBottom) * self.margin
        xmargin = (bestRight - bestLeft) * self.margin
        
        if xmargin == 0: xmargin = 1
        if ymargin == 0: ymargin = 1

        # add margin to border
        if xmargin > 0 and ymargin > 0:
            bestTop    += ymargin
            bestBottom -= ymargin
            bestLeft   -= xmargin
            bestRight  += xmargin
        
        # auto scale
        if bestLeft >= INF:   bestLeft = "*"
        if bestRight <= -INF:  bestRight = "*"
        if bestTop <= -INF:     bestTop = "*"
        if bestBottom >= INF: bestBottom = "*"
        
        if bestLeft == bestRight:
            bestLeft = bestRight = "*"
        if bestTop == bestBottom:
            bestTop = bestBottom = "*"
        
        
        return (bestTop, bestBottom, bestLeft, bestRight)
    
        
    
    def replot(self):
        # do nothing if no data or plotting is not enabled
        if len(self.data) == 0 or \
           not self.enable:
            return  
        
        
        # configure 
        print >>self.stream, "set mouse"
        print >>self.stream, "set mxtics"
        print >>self.stream, "set mytics"
        print >>self.stream, "set mztics"
        
        # margins
        if self.options["margin"]:
            print >>self.stream, "set tmargin %f" % self.options["margin"]
            print >>self.stream, "set bmargin %f" % self.options["margin"]
            print >>self.stream, "set lmargin %f" % self.options["margin"]
            print >>self.stream, "set rmargin %f" % self.options["margin"]
        else:
            print >>self.stream, "set tmargin"
            print >>self.stream, "set bmargin"
            print >>self.stream, "set lmargin"
            print >>self.stream, "set rmargin"
        
        # tics
        if self.options["xtics"] == None:
            print >>self.stream, "set xtics autofreq"
        else:
            print >>self.stream, "set xtics %f" % self.options["xtics"]
        if self.options["ytics"] == None:
            print >>self.stream, "set ytics autofreq"
        else:
            print >>self.stream, "set ytics %f" % self.options["ytics"]
        if self.options["ztics"] == None:
            print >>self.stream, "set ztics autofreq"
        else:
            print >>self.stream, "set ztics %f" % self.options["ztics"]
        
        # log scale
        print >>self.stream, "unset logscale xyz"
        if self.options["xlog"]:
            print >>self.stream, "set logscale x %d" % self.options["xlog"]
        if self.options["ylog"]:
            print >>self.stream, "set logscale y %d" % self.options["ylog"]
        if self.options["zlog"]:
            print >>self.stream, "set logscale z %d" % self.options["zlog"]
        
        # setup ranges
        (maxy, miny, minx, maxx) = self.findRange()
        if self.options["xmin"] != None: minx = self.options["xmin"]
        if self.options["xmax"] != None: maxx = self.options["xmax"]
        if self.options["ymin"] != None: miny = self.options["ymin"]
        if self.options["ymax"] != None: maxy = self.options["ymax"]
        
        print >>self.stream, "set xrange[%s:%s]" % tuple(map(str, [minx, maxx]))
        print >>self.stream, "set yrange[%s:%s]" % tuple(map(str, [miny, maxy]))
        
        # TODO: add range z
        
        # set labels
        if self.options["main"] != "":
            print >>self.stream, "set title \"" + self.options["main"] + "\""            
        if self.options["xlab"] != "":
            print >>self.stream, "set xlabel \"" + self.options["xlab"] + "\""
        if self.options["ylab"] != "":
            print >>self.stream, "set ylabel \"" + self.options["ylab"] + "\""
        if self.options["zlab"] != "":
            print >>self.stream, "set zlabel \"" + self.options["zlab"] + "\""        
        
        # give plot command
        if self.data[0].zlist == []:
            print >>self.stream, "plot ",
        else:
            print >>self.stream, "splot ",
        for i in range(len(self.data)):
            graph = self.data[i]
            
            if graph.options["eqn"]:
                # specify direct equation
                print >>self.stream, graph.options["eqn"], 
            else:
                # specify inline data
                print >>self.stream, "\"-\" ",
            
            # specify style
            if graph.options["style"] != "":
                print >>self.stream, "with ", graph.options["style"],
                
            # specify plot label
            if graph.options["plab"] != "":
                print >>self.stream, " title \""+ graph.options["plab"] +"\"",
            else:
                print >>self.stream, " notitle",

            
            if i < len(self.data) - 1:
                print >>self.stream, ",",
        print >>self.stream, ""
        
        
        # output data  
        for graph in self.data:
            if graph.options["eqn"]:
                continue
            self.outputData(graph.xlist, graph.ylist, graph.zlist, graph.options)
            
        
        # need to make sure gnuplot gets what we have written
        self.stream.flush()
    
    
    def prepareData(self, list1, list2=[], list3=[]):
        if list2 == []:
            list2 = list1
            list1 = range(len(list1))
        
        if len(list1) != len(list2):
            raise Exception("ERROR: arrays are not same length")
        return list1, list2, list3
    
    
    def outputData(self, list1, list2, list3=[], options={}):
        for i in range(len(list1)):
            if list3 == []:
                print >>self.stream, list1[i], \
                                     list2[i],
            else:
                print >>self.stream, list1[i], \
                                     list2[i], \
                                     list3[i],
            
            # error bars
            if "err" in options:
                print >>self.stream, options["err"][i],
            
            if "errlow" in options and "errhi" in options:
                print >>self.stream, options["errlow"][i], options["errhi"][i],
            
            # newline
            print >>self.stream
        print >>self.stream, "e"
    

    def enableOutput(self, enable = True):
        self.enable = enable
        if enable:
            self.stream = os.popen("gnuplot", "w")
    
    
    def plot(self, list1, list2=[], list3=[], **options):
        self.set(**options)
        options2 = copy.copy(self.options)
        options2.update(options)
        
        list1, list2, list3 = self.prepareData(list1, list2, list3)
        self.data.append(self.Plot(list1, list2, list3, options2))
        
        if self.enable:
            self.stream = os.popen("gnuplot", "w")
            self.replot()
    
    
    def plotfunc(self, func, start, end, step, **options):
        x = []
        y = []
        while start < end:
            try:
                y.append(func(start))
                x.append(start)
            except ZeroDivisionError:
                pass
            start += step
        options.setdefault("style", "lines")
        self.plot(x, y, **options)
    
    
    def plotdiag(self, start=None, end=None, **options):
        if start == None:
            start = INF
            
            for graph in self.data:
                if graph.options["eqn"]:
                    continue            
                start = min(start, min(graph.xlist))
                start = min(start, min(graph.ylist))

        if end == None:
            end = -INF
            
            for graph in self.data:
                if graph.options["eqn"]:
                    continue            
                end = max(end, max(graph.xlist))
                end = max(end, max(graph.ylist))
        
        options2 = {"style": "lines",
                    "plab": ""}
        options2.update(options)
        
        self.plot([start, end], [start, end], **options2)
    
    
    
    def gfit(self, func, eqn, params, list1, list2=[], list3=[], ** options):
        """
        all syntax should be valid GNUPLOT syntax
            func - a string of the function call i.e. "f(x)"
            eqn  - a string of a GNUPLOT equation  "a*x**b"
            params - a dictionary of parameters in eqn and their initial values
                   ex: {"a": 1, "b": 3}        
        """
        
        self.set(** options)
    
        print len(list1), len(list2), len(list3)
    
        if not self.enable:
            raise Exception("must be output must be enabled for fitting")
        
        list1, list2, list3 = self.prepareData(list1, list2, list3)
        
        # add data to graph
        self.data.append(self.Plot(list1, list2, list3, copy.copy(self.options)))
        
        
        # perform fitting
        self.stream = os.popen("gnuplot", "w")
        print >>self.stream, "%s = %s" % (func, eqn)
        for param, value in params.items():
            print >>self.stream, "%s = %f" % (param, value)
        print >>self.stream, "fit %s '-' via %s" % \
            (func, ",".join(params.keys()))
        self.outputData(list1, list2, list3)
       
                
        # save and read parameters
        outfile = tempfile(".", "plot", ".txt")        
        print >>self.stream, "save var '%s'" % outfile
        print >>self.stream, "print 'done'"
        self.stream.flush()     
        
        # wait for variable file
        while not os.path.isfile(outfile): pass
        params = self.readParams(outfile)
        os.remove(outfile)
        
        # build eqn for plotting
        paramlist = ""
        for param, value in params.items():
            paramlist += "%s = %s, " % (param, value)
        self.options["eqn"] = paramlist + "%s = %s, %s" % \
            (func, eqn, func)
        self.options["style"] = "lines"
        
        # add fitted eqn to graph
        self.data.append(self.Plot([], [], [], copy.copy(self.options)))
        
        self.replot()
        
    
    def readParams(self, filename):
        params = {}
        
        for line in file(filename):
            if line[0] == "#":
                continue
                
            var, value = line.split("=")
            if not var.startswith("MOUSE_"):
                params[var.replace(" ", "")] = float(value)
        
        return params
    
    

    
    
    
    

def plot(list1, list2=[], list3=[], **options):
    g = options.setdefault("plot", Gnuplot())
    g.plot(list1, list2, list3, **options)
    return g


def plotfunc(func, start, end, step, **options):
    """Plot a function 'func' over the range (start, end)"""
    
    g = options.setdefault("plot", Gnuplot())
    g.plotfunc(func, start, end, step, ** options)
    return g


def plothist(array, ndivs=None, low=None, width=None, **options):
    """Plot a histogram of array"""
    h = hist(array, ndivs, low, width)
    p = options.setdefault("plot", Gnuplot())
    options.setdefault("style", "boxes fill solid")
    
    p.plot(histbins(h[0]), h[1], **options)
    return p


def plotdistrib(array, ndivs=None, low=None, width=None, **options):
    """Plot a distribution of array"""
    d = distrib(array, ndivs, low, width)
    p = options.setdefault("plot", Gnuplot())
    options.setdefault("style", "boxes")
    
    p.plot(histbins(d[0]), d[1], **options)
    return p


def gfit(func, eqn, params, list1, list2=[], list3=[], ** options):
    g = options.setdefault("plot", Gnuplot())
    g.gfit(func, eqn, params, list1, list2, list3, ** options)
    return g



       
    


#=============================================================================

"""
class MultiPlot (Gnuplot):
    def __init__(self, plots, ncols=None, nrows=None, direction="row",
        width=800, height=800):
        Gnuplot.__init__(self)
        
        self.plots = plots
        self.stream = os.popen("gnuplot -geometry %dx%d" % (width, height), "w")
        
        self.nrows = nrows
        self.ncols = ncols
        self.direction = direction
        
        self.replot()

        
    
    def replot(self):
        # determine layout
        nplots = len(self.plots)
        
        if self.nrows == None and self.ncols == None:
            self.ncols = int(math.sqrt(nplots))
        
        if self.ncols != None:
            self.nrows = int(math.ceil(nplots / float(self.ncols))) 
        else:
            self.ncols = int(math.ceil(nplots / float(self.nrows)))

        xstep = 1.0 / self.ncols
        ystep = 1.0 / self.nrows
        ypos = 0
        xpos = 0
        xorigin = 0.0
        yorigin = 1.0
        
        print >>self.stream, "set origin 0, 0"
        print >>self.stream, "set size 1, 1"
        print >>self.stream, "set multiplot"
        for plot in self.plots:
            xpt = xorigin + xpos * xstep
            ypt = yorigin - (ypos+1) * ystep
            
            print >>self.stream, "set origin %f, %f" % (xpt, ypt)
            print >>self.stream, "set size %f, %f" % (xstep, ystep)
            plot.stream = self.stream
            plot.replot()
            
            if self.direction == "row":
                xpos += 1
            elif self.direction == "col":
                ypos += 1
            else:
                raise Exception("unknown direction '%s'" % self.direction)
            
            if xpos >= self.ncols:
                xpos = 0
                ypos += 1
            if ypos >= self.nrows:
                ypos = 0
                xpos += 1
        
        print >>self.stream, "unset multiplot"
"""        
