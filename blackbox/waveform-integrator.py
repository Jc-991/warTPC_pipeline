import numpy as np
import matplotlib.pyplot as plt
import ROOT
import sys
import pandas as pd
import random
from array import array
import csv
import warnings

warnings.filterwarnings("ignore")
#ROOT.gErrorIgnoreLevel = ROOT.kError
ROOT.gErrorIgnoreLevel = ROOT.kFatal

#ROOT.EnableImplicitMT() 
ROOT.gROOT.SetBatch(True)
#ROOT.gErrorIgnoreLevel = ROOT.kWarning
ROOT.gStyle.SetOptStat("emrou")
ROOT.gStyle.SetTitleOffset(1.4, "Y")
ROOT.gStyle.SetPadLeftMargin(0.16)
ROOT.gStyle.SetPadBottomMargin(0.14)

import shutil
import os
import time

data="waveforms.csv"

path=str(sys.argv[1])
directory=str(sys.argv[2])

if os.path.exists(f"{path}/{directory}/waveforms.root"):
    os.remove(f"{path}/{directory}/waveforms.root")

with open(f"{path}/{directory}/settings.csv", "r") as f:
    reader = csv.reader(f)

    for row in reader:
        ID=str(row[0])

#shutil.rmtree("uncut", ignore_errors=True)
#shutil.rmtree("b1-cutting", ignore_errors=True)
#shutil.rmtree("b0-cutting", ignore_errors=True)
#shutil.rmtree("r-cutting", ignore_errors=True)

cutting_folders=["uncut","b1-cutting","b0-cutting","vend-cutting","d-cutting"]
sub_folders=["2d-dists","dists","high","low","waveforms"]

for fold in cutting_folders:
    shutil.rmtree(f"{path}/{directory}/{fold}", ignore_errors=True)
    for sub in sub_folders:
        os.makedirs(f"{path}/{directory}/{fold}/{sub}", exist_ok=True)

filename=f"{path}/{directory}/{data}"

data_array=np.genfromtxt(filename, delimiter ="",skip_header=1)
time_x=data_array[0:,0].astype(np.float64)
time_x = time_x.astype(np.float64)
#print(time)
#wait =input("")
#time= time *1E6

#ROOT.gROOT.SetBatch(True)
sensorB = data_array[0:, 2::2]

def error_drawing(data,num,wnum,folder):

    raw=data[:,num]

    n2=len(raw)
    g2= ROOT.TGraph(n2)

    for jj in range(n2):
        g2.SetPoint(jj, time_x[jj], raw[jj])   # x = index, y = ratio
    
    g2.SetTitle(f"Waveform {num} Baseline;Time (s); Voltage (mV)")
    g2.SetMarkerStyle(20)
    g2.SetMarkerSize(0.6)

    canvas61= ROOT.TCanvas("canvas61","canvas61",800,600)

    g2.Draw("AP")

    canvas61.SaveAs(f"{path}/{directory}/{folder}/waveform{wnum}.pdf")

    canvas61.Close()


def waveform_drawing(data,num,wnum,folder):

    #print(f"waveform{num}")

    raw=data[:,num]

    #first_200=data[0:int(round(imax*0.5)),num]
    first_200=data[0:200,num]

    n1=len(first_200)
    n2=len(raw)
    g1= ROOT.TGraph(n1)
    g2= ROOT.TGraph(n2)

    for j in range(n1):
        g1.SetPoint(j, time_x[j], first_200[j])   # x = index, y = ratio

    for jj in range(n2):
        g2.SetPoint(jj, time_x[jj], raw[jj])   # x = index, y = ratio


    g1.SetTitle(f"Waveform {num} Baseline;Time (s); Voltage (mV)")
    g1.SetMarkerStyle(20)
    g1.SetMarkerSize(0.6)
    g1.SetMarkerColor(ROOT.kRed)
    
    #fit_func = ROOT.TF1("fit_func", "pol0", 0, 1)

    f = ROOT.TF1("f", "pol1", 0, 0.1e-3)

    # pol1: p0 + p1*x
    #f.SetParameters(500.0, 1000.0)  # p0, p1 initial guesses

    
    fit=g1.Fit("f","S Q","",0,g2.GetXaxis().GetXmax())
    b0=fit.Parameter(0)
    b0_err = np.std(first_200)
    b1=fit.Parameter(1)

    #baseline=np.mean(first_200)

    xb = np.array([g1.GetPointX(i) for i in range(g1.GetN())])
    #yb_fit = np.array([f.Eval(xbi) for xbi in xb])#y_fit = f_50_raw.Eval(x)
    yb = np.array([g1.GetPointY(i) for i in range(g1.GetN())])

    rb = np.corrcoef(xb, yb)[0, 1]#ROOT.TMath.CorrelationCoefficient(n, y, x)

    #print(baseline)
    base_subtract= raw - (b0+b1*time_x)

    imax = np.argmax(base_subtract)
    
    tm = float(time_x[imax])#*1E6)

    t200=float(time_x[199])#*1E6)

    integral = np.sum(base_subtract)
    vm=np.max(base_subtract)

    #mid = base_subtract.shape[0] // 2

    threshold = 5*abs(b0_err)
    
    mid = np.argmax(base_subtract > threshold)
    vend = np.min(base_subtract[imax:])

    end_ind=mid

    #print(f"Vstart is {threshold}")
    #print(f"Vend is {vend}")

    #print(f"threshold exceeded at {mid}")

    while base_subtract[end_ind] < vend:
        end_ind+=1
    '''
    if base_subtract[end_ind] > vend:
        print(f"met at {end_ind}")
    else:
        print("not met")
    '''
    ave_50_arr=(base_subtract[mid:end_ind])
        
        
    tstart=float(time_x[mid])#*1E6)

    #print(mid)

    npoints=0
    '''
    idx = np.where(base_subtract >= 0.9*vm)[0]

    ave_50_arr=(base_subtract[mid:idx[0]])
    
    npoints=int(idx[0])-int(mid)
    '''
    if ave_50_arr.size < 5:
        if(mid==999):
            mid=499
            npoints=50
        elif (mid+50 > 999):
            npoints=999-mid
        else:
            npoints=50
        ave_50_arr=(base_subtract[mid:mid+npoints])
    
    #vend=ave_50_arr[-1]

    #vend = np.min(ave_50_arr[imax:])

    #ave_50_arr=(base_subtract[mid:idx[0]])

    npoints=int(len(ave_50_arr))
        
    n4=len(ave_50_arr)
    g4= ROOT.TGraph(n4)

    for jjjj in range(n4):
        g4.SetPoint(jjjj, time_x[mid+jjjj], ave_50_arr[jjjj])   # x = index, y = ratio

    xp = np.array([g4.GetPointX(i) for i in range(g4.GetN())])
    yp = np.array([g4.GetPointY(i) for i in range(g4.GetN())])
    rp = np.corrcoef(xp, yp)[0, 1]#ROOT.TMath.CorrelationCoefficient(n, y, x)

    ave_50_raw=np.mean((raw[mid:mid+npoints]))
    v50=np.mean(base_subtract[mid:mid+npoints])
    ave_50_arr_raw=(raw[mid:mid+npoints])
        
    n5=len(ave_50_arr_raw)
    #print(f"n5 = {n5}")
    #print(f"n4 = {n4}")
    g5= ROOT.TGraph(n5)

    for jjjjj in range(n5):
        g5.SetPoint(jjjjj, time_x[mid+jjjjj], ave_50_arr_raw[jjjjj])   # x = index, y = ratio

    f_50_raw = ROOT.TF1("f_50_raw","pol1",time_x[mid],time_x[mid+npoints])
    fit_50_raw=g5.Fit("f_50_raw","S Q","",time_x[mid],time_x[mid+npoints])
    f_50_raw.SetLineColor(ROOT.kBlue)
    f_50_raw.SetLineWidth(2)


    f_50 = ROOT.TF1("f_50_raw","pol1",time_x[mid],time_x[mid+npoints])
    fit_50=g4.Fit("f_50_raw","S Q","",time_x[mid],time_x[mid+npoints])
    f_50.SetLineColor(ROOT.kBlue)
    f_50.SetLineWidth(2)

    p0_raw=fit_50_raw.Parameter(0)
    p1_raw=fit_50_raw.Parameter(1)/1E9

    p0=fit_50.Parameter(0)
    p1=fit_50.Parameter(1)/1E9

    n = g4.GetN()

    n3=len(base_subtract)
    g3= ROOT.TGraph(n3)

    for jjj in range(n3):
        g3.SetPoint(jjj, time_x[jjj], base_subtract[jjj])   # x = index, y = ratio
        
    #wnum=num

    #a = 500

    d=0
    
    for ff in range (len(ave_50_arr)):

        yi=ave_50_arr[ff]

        x_calc=(yi-p0)/p1

        d+=np.abs(time_x[mid+ff]-x_calc)

    d=d/npoints
    
    g2.SetTitle(f"Waveform {num} Baseline;Time (s); Voltage (mV)")
    g2.SetMarkerStyle(20)
    g2.SetMarkerSize(0.6)

    g1.SetMarkerStyle(20)
    g1.SetMarkerSize(0.6)
    g1.SetMarkerColor(ROOT.kRed)

    g5.SetMarkerStyle(20)
    g5.SetMarkerSize(0.6)
    g5.SetMarkerColor(ROOT.kBlue)

    canvas60= ROOT.TCanvas("canvas6","canvas6",800,600)

    g2.Draw("AP")
    g1.Draw("P")
    g5.Draw("P")
    f_50_raw.Draw("same")
    f.Draw("same")

    line_raw_max = ROOT.TLine(0, np.max(raw), g2.GetXaxis().GetXmax(), np.max(raw))
    line_raw_max.SetLineColor(ROOT.kGreen)
    line_raw_max.SetLineWidth(2)
    line_raw_max.SetLineStyle(3)
    line_raw_max.Draw("same")

    line_raw_50 = ROOT.TLine(0, ave_50_raw, g2.GetXaxis().GetXmax(), ave_50_raw)
    line_raw_50.SetLineColor(ROOT.kGreen+2)
    line_raw_50.SetLineWidth(2)
    line_raw_50.SetLineStyle(3)
    line_raw_50.Draw("same")

    line_raw_start = ROOT.TLine(0, threshold+b0, g2.GetXaxis().GetXmax(), threshold+b0)
    line_raw_start.SetLineColor(ROOT.kCyan+4)
    line_raw_start.SetLineWidth(2)
    line_raw_start.SetLineStyle(2)
    line_raw_start.Draw("same")

    line_raw_end = ROOT.TLine(0, vend+b0, g2.GetXaxis().GetXmax(), vend+b0)
    line_raw_end.SetLineColor(ROOT.kYellow+3)
    line_raw_end.SetLineWidth(2)
    line_raw_end.SetLineStyle(2)
    line_raw_end.Draw("same")
    
    fit_info = ROOT.TLatex()
    fit_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
    fit_info.SetTextSize(0.02)
    fit_info.DrawLatex(0.2, 0.8, "b_{0} = "+str(round(b0,2))+" mV")
    fit_info.DrawLatex(0.2, 0.77, "b_{1} = "+str(round(b1,2))+" mV/s")
    fit_info.DrawLatex(0.2, 0.74, "p_{0} raw = "+str(round(p0_raw,2))+" mV")
    fit_info.DrawLatex(0.2, 0.71, "p_{1} raw = "+str(round(p1_raw,2))+" mV/ns")
    fit_info.DrawLatex(0.2, 0.68, "R_{b} = "+str(round(rb,2)))
    fit_info.DrawLatex(0.2, 0.65, "R_{p} = "+str(round(rp,2)))
    fit_info.DrawLatex(0.2, 0.62, "N_{points} = "+str(npoints))
    fit_info.DrawLatex(0.2, 0.59, "V_{start} = "+str(round(threshold+b0,2)))
    fit_info.DrawLatex(0.2, 0.56, "V_{end} = "+str(round(vend+b0,2)))
    fit_info.DrawLatex(0.2, 0.53, "T_{m} = "+str(round(tm*1E6,2))+"#mus")
    fit_info.DrawLatex(0.2, 0.50, "T_{200} = "+str(round(t200*1E6,2))+"#mus")
    fit_info.DrawLatex(0.2, 0.47, "T_{start} = "+str(round(tstart*1E6,2))+"#mus")
    fit_info.DrawLatex(0.2, 0.44, "V_{m} = "+str(round(vm,2))+"mV")
    fit_info.DrawLatex(0.2, 0.41, "V_{p} = "+str(round(v50,2))+"mV")
    fit_info.DrawLatex(0.2, 0.38, "d = "+str(round(d,2)))

        
    legendraw = ROOT.TLegend(0.6, 0.2, 0.88, 0.4)
    legendraw.AddEntry(g2, "Raw Waveform", "p")   # points
    legendraw.AddEntry(g1, "Baseline Fit Points", "p")   # points
    legendraw.AddEntry(f, "Baseline Fit", "l") # line
    legendraw.AddEntry(line_raw_start, "V_{start}", "l") # line
    legendraw.AddEntry(line_raw_end, "V_{end}", "l") # line
    legendraw.AddEntry(line_raw_50, "V_{p} Raw Value", "l") # line
    legendraw.AddEntry(line_raw_max, "V_{m} Raw Value", "l") # line
    legendraw.AddEntry(g5, "V_{p} Raw Points", "p")   # points
    legendraw.AddEntry(f_50_raw, "V_{p} fit", "l")   # points
    legendraw.Draw()

    canvas60.SaveAs(f"{path}/{directory}/{folder}/waveform{wnum}.pdf")

    canvas60.Close()




def waveform_analysis(data,num,draw_num,folder):

    #print(f"waveform{num}")

    raw=data[:,num]

    #first_200=data[0:int(round(imax*0.5)),num]
    first_200=data[0:200,num]

    n1=len(first_200)
    n2=len(raw)
    g1= ROOT.TGraph(n1)
    g2= ROOT.TGraph(n2)

    for j in range(n1):
        g1.SetPoint(j, time_x[j], first_200[j])   # x = index, y = ratio

    for jj in range(n2):
        g2.SetPoint(jj, time_x[jj], raw[jj])   # x = index, y = ratio


    g1.SetTitle(f"Waveform {num} Baseline;Time (s); Voltage (mV)")
    g1.SetMarkerStyle(20)
    g1.SetMarkerSize(0.6)
    g1.SetMarkerColor(ROOT.kRed)
    
    #fit_func = ROOT.TF1("fit_func", "pol0", 0, 1)

    f = ROOT.TF1("f", "pol1", 0, 0.1e-3)

    # pol1: p0 + p1*x
    #f.SetParameters(1000.0, 1000.0)  # p0, p1 initial guesses

    
    fit=g1.Fit("f","S Q","",0,g2.GetXaxis().GetXmax())
    b0=fit.Parameter(0)
    b0_err = np.std(first_200)
    b1=fit.Parameter(1)

    #baseline=np.mean(first_200)

    xb = np.array([g1.GetPointX(i) for i in range(g1.GetN())])
    #yb_fit = np.array([f.Eval(xbi) for xbi in xb])#y_fit = f_50_raw.Eval(x)
    yb = np.array([g1.GetPointY(i) for i in range(g1.GetN())])

    rb = np.corrcoef(xb, yb)[0, 1]#ROOT.TMath.CorrelationCoefficient(n, y, x)

    #print(baseline)
    base_subtract= raw - (b0+b1*time_x)

    imax = np.argmax(base_subtract)
    
    tm = float(time_x[imax])#*1E6)

    t200=float(time_x[199])#*1E6)

    integral = np.sum(base_subtract)
    vm=np.max(base_subtract)

    #mid = base_subtract.shape[0] // 2

    threshold = 5*abs(b0_err)
    
    mid = np.argmax(base_subtract > threshold)
    vend = np.min(base_subtract[imax:])

    end_ind=mid

    #print(f"Vstart is {threshold}")
    #print(f"Vend is {vend}")

    #print(f"threshold exceeded at {mid}")

    while base_subtract[end_ind] < vend:
        end_ind+=1
    '''
    if base_subtract[end_ind] > vend:
        print(f"met at {end_ind}")
    else:
        print("not met")
    '''
    ave_50_arr=(base_subtract[mid:end_ind])

    tend = float(time_x[end_ind])#*1E6)
        
    tstart=float(time_x[mid])#*1E6)

    dt=np.abs(tend-tstart)

    #print(f"{tstart} at {num}")

    #print(mid)

    npoints=0
    '''
    idx = np.where(base_subtract >= 0.9*vm)[0]

    ave_50_arr=(base_subtract[mid:idx[0]])
    
    npoints=int(idx[0])-int(mid)
    '''

    #print(f"{mid} {mid.dtype} at {num}")

    #print(f"{type(999)}")
    
    if ave_50_arr.size < 5:
        if(mid==999):
            mid=499
            npoints=50
        elif (mid+50 > 999):
            npoints=999-mid
        else:
            npoints=50
        ave_50_arr=(base_subtract[mid:mid+npoints])

    #print(f"{mid} + {npoints} at {num}")
    
    #vend=ave_50_arr[-1]

    #vend = np.min(ave_50_arr[imax:])

    #ave_50_arr=(base_subtract[mid:idx[0]])

    npoints=int(len(ave_50_arr))

    #print(f"{npoints} at {num}")
    
    n4=len(ave_50_arr)
    g4= ROOT.TGraph(n4)

    for jjjj in range(n4):
        g4.SetPoint(jjjj, time_x[mid+jjjj], ave_50_arr[jjjj])   # x = index, y = ratio

    xp = np.array([g4.GetPointX(i) for i in range(g4.GetN())])
    yp = np.array([g4.GetPointY(i) for i in range(g4.GetN())])
    rp = np.corrcoef(xp, yp)[0, 1]#ROOT.TMath.CorrelationCoefficient(n, y, x)

    ave_50_raw=np.mean((raw[mid:mid+npoints]))
    v50=np.mean(base_subtract[mid:mid+npoints])
    ave_50_arr_raw=(raw[mid:mid+npoints])
        
    n5=len(ave_50_arr_raw)
    #print(f"n5 = {n5}")
    #print(f"n4 = {n4}")
    g5= ROOT.TGraph(n5)

    for jjjjj in range(n5):
        g5.SetPoint(jjjjj, time_x[mid+jjjjj], ave_50_arr_raw[jjjjj])   # x = index, y = ratio

    f_50_raw = ROOT.TF1("f_50_raw","pol1",time_x[mid],time_x[mid+npoints])
    fit_50_raw=g5.Fit("f_50_raw","S Q","",time_x[mid],time_x[mid+npoints])
    f_50_raw.SetLineColor(ROOT.kBlue)
    f_50_raw.SetLineWidth(2)


    f_50 = ROOT.TF1("f_50","pol1",time_x[mid],time_x[mid+npoints])
    fit_50=g4.Fit("f_50","S Q","",time_x[mid],time_x[mid+npoints])
    f_50.SetLineColor(ROOT.kBlue)
    f_50.SetLineWidth(2)

    p0_raw=fit_50_raw.Parameter(0)
    p1_raw=fit_50_raw.Parameter(1)/1E9

    p0=fit_50.Parameter(0)
    p1=fit_50.Parameter(1)/1E9

    n = g4.GetN()

    n3=len(base_subtract)
    g3= ROOT.TGraph(n3)

    for jjj in range(n3):
        g3.SetPoint(jjj, time_x[jjj], base_subtract[jjj])   # x = index, y = ratio
        
    #wnum=num

    #a = 500

    d=0
    
    for ff in range (len(ave_50_arr)):

        yi=ave_50_arr[ff]

        x_calc=(yi-p0)/p1

        d+=np.abs(time_x[mid+ff]-x_calc)

    d=d/npoints
    '''
    if int(fit_50.Status()) != 0:
        raise RuntimeError(f"Fit failed with status {fit_result.Status()}")

    if int(fit_50_raw.Status()) != 0:
        raise RuntimeError(f"Fit failed with status {fit_result.Status()}")

    if int(fit.Status()) != 0:
        raise RuntimeError(f"Fit failed with status {fit_result.Status()}")
    '''
    if num in draw_num:

        wnum=np.where(draw_num == num)[0][0]
    
        g1.SetTitle(f"Waveform {num} Baseline;Time (s); Voltage (mV)")
        g1.SetMarkerStyle(20)
        g1.SetMarkerSize(0.6)
        g1.SetMarkerColor(ROOT.kRed)
    
        g2.SetTitle(f"Full Waveform {num};Time (s); Voltage (mV)")
        g2.SetMarkerStyle(20)
        g2.SetMarkerSize(0.6)

        canvas20= ROOT.TCanvas("canvas20","canvas20",800,600)####PLOT FOR FIRST 200 + BASELINE FIT(DONE)

        g1.Draw("AP")
        fit_info = ROOT.TLatex()
        fit_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
        fit_info.SetTextSize(0.02)
        fit_info.DrawLatex(0.2, 0.8, "b_{0} = "+str(round(b0,2))+" mV")
        fit_info.DrawLatex(0.2, 0.77, "b_{1} = "+str(round(b1,2))+" mV/s")
        fit_info.DrawLatex(0.2, 0.74, "R_{b} = "+str(round(rb,2)))

        canvas20.SaveAs(f"{path}/{directory}/{folder}/waveform{wnum}.pdf")

        canvas20.Close()

        g4.SetTitle(f"Waveform {num} Zeroed;Time (s); Voltage (mV)")
        g4.SetMarkerStyle(20)
        g4.SetMarkerSize(0.6)
        g4.SetMarkerColor(ROOT.kBlue)

        g5.SetTitle(f"Waveform {str(num)} Zeroed;Time (s); Voltage (mV)")
        g5.SetMarkerStyle(20)
        g5.SetMarkerSize(0.6)
        g5.SetMarkerColor(ROOT.kBlue)

        canvas30 = ROOT.TCanvas("canvas30","canvas30",800,600)###PLOT FOR FULL RAW WAVEFORM + BASELINE FIT

        g2.Draw("AP")
        g1.Draw("P")
        g5.Draw("P")
        f_50_raw.Draw("same")
        f.Draw("same")
    
        line_raw_max = ROOT.TLine(0, np.max(raw), g2.GetXaxis().GetXmax(), np.max(raw))
        line_raw_max.SetLineColor(ROOT.kGreen)
        line_raw_max.SetLineWidth(2)
        line_raw_max.SetLineStyle(3)
        line_raw_max.Draw("same")

        line_raw_50 = ROOT.TLine(0, ave_50_raw, g2.GetXaxis().GetXmax(), ave_50_raw)
        line_raw_50.SetLineColor(ROOT.kGreen+2)
        line_raw_50.SetLineWidth(2)
        line_raw_50.SetLineStyle(3)
        line_raw_50.Draw("same")

        line_raw_start = ROOT.TLine(0, threshold+b0, g2.GetXaxis().GetXmax(), threshold+b0)
        line_raw_start.SetLineColor(ROOT.kCyan+3)
        line_raw_start.SetLineWidth(2)
        line_raw_start.SetLineStyle(2)
        line_raw_start.Draw("same")

        line_raw_end = ROOT.TLine(0, vend+b0, g2.GetXaxis().GetXmax(), vend+b0)
        line_raw_end.SetLineColor(ROOT.kYellow+3)
        line_raw_end.SetLineWidth(2)
        line_raw_end.SetLineStyle(2)
        line_raw_end.Draw("same")
    
        fit_info = ROOT.TLatex()
        fit_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
        fit_info.SetTextSize(0.02)
        fit_info.DrawLatex(0.2, 0.8, "b_{0} = "+str(round(b0,2))+" mV")
        fit_info.DrawLatex(0.2, 0.77, "b_{1} = "+str(round(b1,2))+" mV/s")
        fit_info.DrawLatex(0.2, 0.74, "p_{0} raw = "+str(round(p0_raw,2))+" mV")
        fit_info.DrawLatex(0.2, 0.71, "p_{1} raw = "+str(round(p1_raw,2))+" mV/ns")
        fit_info.DrawLatex(0.2, 0.68, "R_{b} = "+str(round(rb,2)))
        fit_info.DrawLatex(0.2, 0.65, "R_{p} = "+str(round(rp,2)))
        fit_info.DrawLatex(0.2, 0.62, "N_{points} = "+str(npoints))
        fit_info.DrawLatex(0.2, 0.59, "V_{start} = "+str(round(threshold+b0,2)))
        fit_info.DrawLatex(0.2, 0.56, "V_{end} = "+str(round(vend+b0,2)))
        fit_info.DrawLatex(0.2, 0.53, "T_{m} = "+str(round(tm*1E6,2))+"#mus")
        fit_info.DrawLatex(0.2, 0.50, "T_{200} = "+str(round(t200*1E6,2))+"#mus")
        fit_info.DrawLatex(0.2, 0.47, "T_{start} = "+str(round(tstart*1E6,2))+"#mus")
        fit_info.DrawLatex(0.2, 0.44, "V_{m} = "+str(round(vm,2))+"mV")
        fit_info.DrawLatex(0.2, 0.41, "V_{p} = "+str(round(v50,2))+"mV")
        fit_info.DrawLatex(0.2, 0.38, "d = "+str(round(d,2)))

        legendraw = ROOT.TLegend(0.6, 0.2, 0.88, 0.4)
        legendraw.AddEntry(g2, "Raw Waveform", "p")   # points
        legendraw.AddEntry(g1, "Baseline Fit Points", "p")   # points
        legendraw.AddEntry(f, "Baseline Fit", "l") # line
        legendraw.AddEntry(line_raw_start, "V_{start}", "l") # line
        legendraw.AddEntry(line_raw_end, "V_{end}", "l") # line
        legendraw.AddEntry(line_raw_50, "V_{p} Raw Value", "l") # line
        legendraw.AddEntry(line_raw_max, "V_{m} Raw Value", "l") # line
        legendraw.AddEntry(g5, "V_{p} Raw Points", "p")   # points
        legendraw.AddEntry(f_50_raw, "V_{p} fit", "l")   # points
        legendraw.Draw()

        canvas30.SaveAs(f"{path}/{directory}/{folder}/waveform{wnum}_full.pdf")

        canvas30.Close()

        canvas40= ROOT.TCanvas("canvas40","canvas40",800,600)

        g4.SetTitle(f"Waveform {str(num)} V_{{N}} Fit;Time (s); Voltage (mV)")
        g4.Draw("AP")
        f_50.Draw("same")
        fit_info = ROOT.TLatex()
        fit_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
        fit_info.SetTextSize(0.03)
        fit_info.DrawLatex(0.2, 0.8, "p_{0} = "+str(round(p0,2))+" mV")
        fit_info.DrawLatex(0.2, 0.75, "p_{1} = "+str(round(p1,2))+" mV/ns")
        fit_info.DrawLatex(0.2, 0.7, "R_{p} = "+str(round(rp,2)))
        fit_info.DrawLatex(0.2, 0.65, "N_{points} = "+str(npoints))

        canvas40.SaveAs(f"{path}/{directory}/{folder}/waveform{str(wnum)}_V50_fit.pdf")
    
        canvas40.Close()

        g3.SetTitle(f"Waveform {str(num) } Zeroed;Time (s); Voltage (mV)")
        g3.SetMarkerStyle(20)
        g3.SetMarkerSize(0.6)
        
        canvas49= ROOT.TCanvas("canvas49","canvas49",800,600)###PLOT FOR V50 FIT ONLY

        g3.Draw("AP")
        g4.Draw("P")
        f_50.Draw("same")

        fit_info = ROOT.TLatex()
        fit_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
        fit_info.SetTextSize(0.02)
        fit_info.DrawLatex(0.2, 0.8, "b_{0} = "+str(round(b0,2))+" mV")
        fit_info.DrawLatex(0.2, 0.77, "b_{1} = "+str(round(b1,2))+" mV/s")
        fit_info.DrawLatex(0.2, 0.74, "p_{0} raw = "+str(round(p0_raw,2))+" mV")
        fit_info.DrawLatex(0.2, 0.71, "p_{1} raw = "+str(round(p1_raw,2))+" mV/ns")
        fit_info.DrawLatex(0.2, 0.68, "R_{b} = "+str(round(rb,2)))
        fit_info.DrawLatex(0.2, 0.65, "R_{p} = "+str(round(rp,2)))
        fit_info.DrawLatex(0.2, 0.62, "N_{points} = "+str(npoints))
        fit_info.DrawLatex(0.2, 0.59, "V_{start} = "+str(round(threshold+b0,2)))
        fit_info.DrawLatex(0.2, 0.56, "V_{end} = "+str(round(vend,2)))
        fit_info.DrawLatex(0.2, 0.53, "T_{m} = "+str(round(tm*1E6,2))+"#mus")
        fit_info.DrawLatex(0.2, 0.50, "T_{200} = "+str(round(t200*1E6,2))+"#mus")
        fit_info.DrawLatex(0.2, 0.47, "T_{start} = "+str(round(tstart*1E6,2))+"#mus")
        fit_info.DrawLatex(0.2, 0.44, "V_{m} = "+str(round(vm,2))+"mV")
        fit_info.DrawLatex(0.2, 0.41, "V_{p} = "+str(round(v50,2))+"mV")
        fit_info.DrawLatex(0.2, 0.38, "d = "+str(round(d,2)))

        line50 = ROOT.TLine(0, v50, g3.GetXaxis().GetXmax(), v50)
        line50.SetLineColor(ROOT.kGreen+2)
        line50.SetLineWidth(2)
        line50.SetLineStyle(3)
        line50.Draw("same")

        linemax = ROOT.TLine(0, vm , g3.GetXaxis().GetXmax(), vm)
        linemax.SetLineColor(ROOT.kGreen)
        linemax.SetLineWidth(2)
        linemax.SetLineStyle(3)
        linemax.Draw("same")
        
        line_start = ROOT.TLine(0, threshold, g3.GetXaxis().GetXmax(), threshold)
        line_start.SetLineColor(ROOT.kCyan+3)
        line_start.SetLineWidth(2)
        line_start.SetLineStyle(2)
        line_start.Draw("same")

        line_end = ROOT.TLine(0, vend, g3.GetXaxis().GetXmax(), vend)
        line_end.SetLineColor(ROOT.kYellow+3)
        line_end.SetLineWidth(2)
        line_end.SetLineStyle(2)
        line_end.Draw("same")
        
        legend0 = ROOT.TLegend(0.6, 0.2, 0.88, 0.4)
        legend0.AddEntry(g3, "Zeroes Waveform", "p")   # points
        legend0.AddEntry(line_start, "V_{start} Value", "l") # line
        legend0.AddEntry(line_end, "V_{end} Value", "l") # line
        legend0.AddEntry(line50, "V_{p} Value", "l") # line
        legend0.AddEntry(linemax, "V_{peak} Value", "l") # line
        legend0.AddEntry(f_50,"V_{p} Fit","l")
        legend0.AddEntry(g4, "V_{p} points", "p")   # points
        legend0.Draw()
        
        canvas49.SaveAs(f"{path}/{directory}/{folder}/waveform{wnum}_subtracted.pdf")
        
    return b0, b1, rb, p0, p1, rp, v50, vm, npoints, threshold, tm, t200, tstart, vend, d, dt

def NormalizeXSlices(hist2d):
    h_norm = hist2d.Clone(hist2d.GetName() + "_norm")
    h_norm.SetDirectory(0)
    h_norm.Reset()
    for ix in range(1, hist2d.GetNbinsX() + 1):
        # Find maximum in this X slice
        max_content = max(
            hist2d.GetBinContent(ix, iy)
            for iy in range(1, hist2d.GetNbinsY() + 1)
        )
        if max_content > 0:
            for iy in range(1, hist2d.GetNbinsY() + 1):
                content = hist2d.GetBinContent(ix, iy)
                h_norm.SetBinContent(ix, iy, content / max_content)
    return h_norm


def plotting(outlier_list,title_list,x_list,name_list,cut_no,res_dir,good_list):

    ROOT.gErrorIgnoreLevel = ROOT.kWarning
    ROOT.gStyle.SetOptStat("emrou")

    #numbers=np.linspace(0, 12000, 41)
    numbers=[10000000000000000,200000000000000000000]
    b0_arr=[]
    b1_arr=[]
    rb_arr=[]
    p0_arr=[]
    p1_arr=[]
    rp_arr=[]
    v50_arr=[]
    vm_arr=[]
    n_array=[]
    thres_arr=[]
    p1_div_vm_arr=[]
    p1_div_v50_arr=[]
    tm_arr=[]
    t200_arr=[]
    tstart_arr=[]
    tstart_minus_t200=[]
    tm_minus_tstart=[]
    k_arr=[]
    r_arr=[]
    vend_arr=[]
    d_arr=[]
    dV_arr=[]
    dt_arr=[]

    for kk in range (len(good_list)):
        #if kk not in outlier_list:
            res_b0, res_b1, res_rb, res_p0, res_p1, res_rp, res_v50, res_vm, res_n, res_thres, res_tm, res_t200, res_tstart, res_vend, res_d,res_dt = waveform_analysis(sensorB,int(good_list[kk]),numbers,f"{res_dir}/waveforms")#data,num,drawnum,folder
            b0_arr.append(res_b0)
            b1_arr.append(res_b1)
            rb_arr.append(res_rb)
            p0_arr.append(res_p0)
            p1_arr.append(res_p1)
            rp_arr.append(res_rp)
            v50_arr.append(res_v50)
            vm_arr.append(res_vm)
            n_array.append(res_n)
            thres_arr.append(res_thres)
            p1_div_vm_arr.append(res_p1/res_vm)
            p1_div_v50_arr.append(res_p1/res_v50)
            tm_arr.append(res_tm)
            t200_arr.append(res_t200)
            tstart_arr.append(res_tstart)
            tstart_minus_t200.append(res_tstart-res_t200)
            tm_minus_tstart.append(res_tm-res_tstart)
            k=(res_vm-res_thres)/(res_tm-res_tstart)
            k_arr.append(k)
            r_arr.append(res_p1/k)
            vend_arr.append(res_vend)
            d_arr.append(res_d)
            dV_arr.append(res_vend-res_thres)
            dt_arr.append(res_dt)
            #print(f"good at {good_list[kk]}")
            #print(kk)


    b0_arr=np.array(b0_arr)
    b1_arr=np.array(b1_arr)
    p0_arr=np.array(p0_arr)
    p1_arr=np.array(p1_arr)
    rb_arr=np.array(rb_arr)
    rp_arr=np.array(rp_arr)
    v50_arr=np.array(v50_arr)
    vm_arr=np.array(vm_arr)
    n_array=np.array(n_array)
    thres_arr=np.array(thres_arr)
    p1_div_vm_arr=np.array(p1_div_vm_arr)
    p1_div_v50_arr=np.array(p1_div_v50_arr)
    tm_arr=np.array(tm_arr)
    t200_arr=np.array(t200_arr)
    tstart_arr=np.array(tstart_arr)
    tstart_minus_t200=np.array(tstart_minus_t200)
    tm_minus_tstart=np.array(tm_minus_tstart)
    k_arr=np.array(k_arr)
    r_arr=np.array(r_arr)
    vend_arr=np.array(vend_arr)
    d_arr=np.array(d_arr)
    dV_arr=np.array(dV_arr)
    dt_arr=np.array(dt_arr)


    arr_of_arr=[b0_arr,b1_arr,p0_arr,p1_arr,rp_arr,rb_arr,v50_arr,vm_arr,n_array,thres_arr,p1_div_vm_arr,p1_div_v50_arr,tm_arr,t200_arr,tstart_arr,tstart_minus_t200,tm_minus_tstart,k_arr,r_arr,vend_arr,d_arr,dV_arr,dt_arr]

    bins=[50,50,50,50,50,50,50,50,120,50,50,50,50,50,50,50,50,50,50,50,50,50,50]
    
    c = ROOT.TCanvas("c", "c", 800, 600)

    f = ROOT.TFile("Distributions_uncut.root", "RECREATE")

    for qq in range(len(arr_of_arr)):

        low = np.percentile(arr_of_arr[qq], 0.5)
        high = np.percentile(arr_of_arr[qq], 99.5)
        
        margin = 0.1 * (high - low)

        xmin = low - margin
        xmax = high + margin

        h=ROOT.TH1F(f"{title_list[qq]}",f"{title_list[qq]};{x_list[qq]};Counts",bins[qq],xmin,xmax)

        h.SetFillColor(ROOT.kCyan)
        h.SetLineColor(ROOT.kBlack)
        
        for x in arr_of_arr[qq]:
            h.Fill(x)

        h.Draw("HIST")

        h.Write()
        
        ID_info = ROOT.TLatex()
        ID_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
        ID_info.SetTextSize(0.02)
        ID_info.DrawLatex(0.2, 0.8, f"ID:{ID}")
        
        c.Modified()
        c.Update()
        
        c.SaveAs(f"{path}/{directory}/{res_dir}/dists/{name_list[qq]}.pdf")

        c.Close()

    b0_n=len(b0_arr)
    b1_n=len(b1_arr)
    n_n1=len(n_array)
    b0_g=ROOT.TGraph(b0_n)
    b1_g=ROOT.TGraph(b1_n)
    n_g1=ROOT.TGraph(n_n1)

    for y in range(b0_n):
        b0_g.SetPoint(y, y, b0_arr[y])   # x = index, y = ratio

    for yy in range(b1_n):
        b1_g.SetPoint(yy, yy, b1_arr[yy])   # x = index, y = ratio

    for yyy in range(n_n1):
        n_g1.SetPoint(yyy, yyy, n_array[yyy])   # x = index, y = ratio


    c_b0g = ROOT.TCanvas("c_b0g", "c_b0g", 800, 600)

    b0_g.SetTitle("b_{0} Monitoring;Waveform Number;b_{0} Value (mV)")
        
    b0_g.Draw("AP")

    ID_info = ROOT.TLatex()
    ID_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
    ID_info.SetTextSize(0.02)
    ID_info.DrawLatex(0.2, 0.8, f"ID:{ID}")

    c_b0g.Modified()
    c_b0g.Update()
        
    c_b0g.SaveAs(f"{path}/{directory}/{res_dir}/dists/b0-monitoring.pdf")
        
    c_b1g = ROOT.TCanvas("c_b1g", "c_b1g", 800, 600)
        
    b1_g.SetTitle("b_{1} Monitoring;Waveform Number;b_{1} Value (mV/ms)")
        
    b1_g.Draw("AP")

    ID_info = ROOT.TLatex()
    ID_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
    ID_info.SetTextSize(0.02)
    ID_info.DrawLatex(0.2, 0.8, f"ID:{ID}")
        
    c_b1g.Modified()
    c_b1g.Update()
        
    c_b1g.SaveAs(f"{path}/{directory}/{res_dir}/dists/b1-monitoring.pdf")

    c_n1 = ROOT.TCanvas("c_n1", "c_n1", 800, 600)
        
    n_g1.SetTitle("N_{points} Monitoring;Waveform Number;N_{points} Value")
        
    n_g1.Draw("AP")

    ID_info = ROOT.TLatex()
    ID_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
    ID_info.SetTextSize(0.02)
    ID_info.DrawLatex(0.2, 0.8, f"ID:{ID}")
        
    c_n1.Modified()
    c_n1.Update()

    c_n1.SaveAs(f"{path}/{directory}/{res_dir}/dists/npoints-monitoring.pdf")
        
    ROOT.gStyle.SetOptStat(0)

    c1 = ROOT.TCanvas("c1", "c1", 800, 600)
    
    for mm in range(len(arr_of_arr)):
        for nn in range(len(arr_of_arr)):

            if (mm != nn):

                lowx = np.percentile(arr_of_arr[nn], 0.5)
                highx = np.percentile(arr_of_arr[nn], 99.5)

                marginx = 0.1 * (highx - lowx)

                xmin = lowx - marginx
                xmax = highx + marginx
            
                lowy = np.percentile(arr_of_arr[mm], 0.5)
                highy = np.percentile(arr_of_arr[mm], 99.5)
                    
                marginy = 0.1 * (highy - lowy)
            
                ymin = lowy - marginy
                ymax = highy + marginy

                h2 = ROOT.TH2F(f"h2_{mm}_{nn}",f"{x_list[mm]} vs {x_list[nn]};{x_list[nn]};{x_list[mm]}", bins[nn], xmin, xmax, bins[mm], ymin, ymax)

                for x, y in zip(arr_of_arr[nn], arr_of_arr[mm]):
                    h2.Fill(x,y)
                        
                h2_norm=NormalizeXSlices(h2)

                h2_norm.Draw("COLZ")

                ID_info = ROOT.TLatex()
                ID_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
                ID_info.SetTextSize(0.02)
                ID_info.DrawLatex(0.2, 0.8, f"ID:{ID}")

                c1.Modified()
                c1.Update()
                    
                c1.SaveAs(f"{path}/{directory}/{res_dir}/2d-dists/{name_list[mm]}_vs_{name_list[nn]}.pdf")

                h2.Delete()
                h2_norm.Delete()
                

    next_cut=arr_of_arr[cut_no]
                    
    return next_cut


def cutting(cutting_arr,title_list,x_list,name_list,num_val,res_dir,main_arr,good_waveforms):

    #print(f"Length of good waveforms is: {len(good_waveforms)}")
    #print(f"Length of cutting array is {len(cutting_arr)}")

    ROOT.gErrorIgnoreLevel = ROOT.kWarning
    ROOT.gStyle.SetOptStat("emrou")

    lowx = np.percentile(cutting_arr, 0.5)
    highx = np.percentile(cutting_arr, 99.5)

    marginx = 0.1 * (highx - lowx)

    xmin = lowx - marginx
    xmax = highx + marginx

    hb=ROOT.TH1F(f"{title_list[num_val]}",f"{title_list[num_val]};{x_list[num_val]};Counts",50,xmin,xmax)

    hb.SetFillColor(ROOT.kCyan)
    hb.SetLineColor(ROOT.kBlack)
    
    for xb in cutting_arr:
        hb.Fill(xb)

    hb.Fit("gaus","Q")
    fit = hb.GetFunction("gaus")

    chi2 = fit.GetChisquare()
    ndf = fit.GetNDF()

    mean  = fit.GetParameter(1)
    sigma = fit.GetParameter(2)
    
    cb = ROOT.TCanvas("cb", "cb", 800, 600)
    hb.Draw("HIST")
    fit.Draw("same")
    ID_info = ROOT.TLatex()
    ID_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
    ID_info.SetTextSize(0.02)
    ID_info.DrawLatex(0.2, 0.8, f"ID:{ID}")
    
    N=2

    upper=mean+N*sigma
    lower=mean-N*sigma
    
    line2sigplus = ROOT.TLine(mean+N*sigma, 0, mean+N*sigma, hb.GetMaximum())
    line2sigplus.SetLineColor(ROOT.kGreen+2)
    line2sigplus.SetLineWidth(2)
    line2sigplus.Draw("same")

    line2sigminus = ROOT.TLine(mean-N*sigma, 0, mean-N*sigma,hb.GetMaximum())
    line2sigminus.SetLineColor(ROOT.kGreen+2)
    line2sigminus.SetLineWidth(2)
    line2sigminus.Draw("same")
    
    latex = ROOT.TLatex()
    latex.SetNDC(True)  # normalized coordinates
    latex.SetTextSize(0.03)

    latex.DrawLatex(0.60, 0.85, f"#chi^{{2}}/NDF = {chi2:.1f}/{ndf}")
    latex.DrawLatex(0.60, 0.80, f"#mu = {mean:.3f}")
    latex.DrawLatex(0.60, 0.75, f"#sigma = {sigma:.3f}")
    
    cb.Modified()
    cb.Update()
    
    cb.SaveAs(f"{path}/{directory}/{res_dir}/dists/{name_list[num_val]}.pdf")
    
    cut_low = [good_waveforms[iii] for iii, xxx in enumerate(cutting_arr)
       if xxx < lower]

    cut_high = [good_waveforms[iii] for iii, xxx in enumerate(cutting_arr)
       if xxx > upper]

    return cut_low,cut_high



def cutting_r(cutting_arr,title_list,x_list,name_list,num_val,res_dir,main_arr,good_waveforms,check_arr):

    #print(f"Length of good waveforms is: {len(good_waveforms)}")
    #print(f"Length of cutting array is {len(cutting_arr)}")

    ROOT.gErrorIgnoreLevel = ROOT.kWarning
    ROOT.gStyle.SetOptStat("emrou")

    lowx = np.percentile(cutting_arr, 0.5)
    highx = np.percentile(cutting_arr, 99.5)

    marginx = 0.1 * (highx - lowx)

    xmin = lowx - marginx
    xmax = highx + marginx

    hb=ROOT.TH1F(f"{title_list[num_val]}",f"{title_list[num_val]};{x_list[num_val]};Counts",50,xmin,xmax)

    hb.SetFillColor(ROOT.kCyan)
    hb.SetLineColor(ROOT.kBlack)
    
    for xb in cutting_arr:
        hb.Fill(xb)

    hb.Fit("gaus")
    fit = hb.GetFunction("gaus")

    chi2 = fit.GetChisquare()
    ndf = fit.GetNDF()

    mean  = fit.GetParameter(1)
    sigma = fit.GetParameter(2)
    
    cb = ROOT.TCanvas("cb", "cb", 800, 600)
    hb.Draw("HIST")
    fit.Draw("same")
    
    N=2

    upper=mean+3*sigma
    lower=mean-N*sigma
    
    line2sigplus = ROOT.TLine(mean+3*sigma, 0, mean+3*sigma, hb.GetMaximum())
    line2sigplus.SetLineColor(ROOT.kGreen+2)
    line2sigplus.SetLineWidth(2)
    line2sigplus.Draw("same")

    line2sigminus = ROOT.TLine(mean-N*sigma, 0, mean-N*sigma,hb.GetMaximum())
    line2sigminus.SetLineColor(ROOT.kGreen+2)
    line2sigminus.SetLineWidth(2)
    line2sigminus.Draw("same")
    
    latex = ROOT.TLatex()
    latex.SetNDC(True)  # normalized coordinates
    latex.SetTextSize(0.03)

    latex.DrawLatex(0.60, 0.85, f"#chi^{{2}}/NDF = {chi2:.1f}/{ndf}")
    latex.DrawLatex(0.60, 0.80, f"#mu = {mean:.3f}")
    latex.DrawLatex(0.60, 0.75, f"#sigma = {sigma:.3f}")
    
    cb.Modified()
    cb.Update()
    
    cb.SaveAs(f"{path}/{directory}/{res_dir}/dists/{name_list[num_val]}.pdf")
    
    cut_low = [good_waveforms[iii] for iii, xxx in enumerate(cutting_arr)
               if (xxx < lower) and (check_arr[iii] < 3900.0)]

    cut_high = [good_waveforms[iii] for iii, xxx in enumerate(cutting_arr)
                if (xxx > upper) and (check_arr[iii] < 3900.0)]

    return cut_low,cut_high




def error_cutting(res_dir,good_list):

    failed_waveforms = []

    ROOT.gErrorIgnoreLevel = ROOT.kWarning
    ROOT.gStyle.SetOptStat("emrou")

    numbers=[500000000000,2000000000000]

    #numbers=np.linspace(0, 12000, 21)

    for kk in range (len(good_list)):
        #if kk not in outlier_list:
        try:
            with np.errstate(all='raise'):
                res_b0, res_b1, res_rb, res_p0, res_p1, res_rp, res_v50, res_vm, res_n, res_thres, res_tm, res_t200, res_tstart, res_vend, res_d = waveform_analysis(sensorB,int(good_list[kk]),numbers,f"{res_dir}/waveforms")#data,num,drawnum,folder
                #print(res_b0, res_b1, res_rb, res_p0, res_p1, res_rp, res_v50, res_vm, res_n, res_thres, res_tm, res_t200, res_tstart, res_vend, res_d)
                k=(res_vm-res_thres)/(res_tm-res_tstart)
                r=res_p1/k
                #print(k)
                #print(r)
                #wait=input("")

        except Exception as e:
            #print(f"Waveform {kk} failed: {e}")
            failed_waveforms.append(kk)

    return failed_waveforms

    


def get_dist(cut_no,res_dir,good_list):

    ROOT.gErrorIgnoreLevel = ROOT.kWarning
    ROOT.gStyle.SetOptStat("emrou")

    numbers=[1000000000000,2000000000000]

    b0_arr=[]
    b1_arr=[]
    rb_arr=[]
    p0_arr=[]
    p1_arr=[]
    rp_arr=[]
    v50_arr=[]
    vm_arr=[]
    n_array=[]
    thres_arr=[]
    p1_div_vm_arr=[]
    p1_div_v50_arr=[]
    tm_arr=[]
    t200_arr=[]
    tstart_arr=[]
    tstart_minus_t200=[]
    tm_minus_tstart=[]
    k_arr=[]
    r_arr=[]
    vend_arr=[]
    d_arr=[]
    dV_arr=[]

    for kk in range (len(good_list)):
        #if kk not in outlier_list:
            res_b0, res_b1, res_rb, res_p0, res_p1, res_rp, res_v50, res_vm, res_n, res_thres, res_tm, res_t200, res_tstart, res_vend, res_d, res_dt = waveform_analysis(sensorB,int(good_list[kk]),numbers,f"{res_dir}/waveforms")#data,num,drawnum,folder
            b0_arr.append(res_b0)
            b1_arr.append(res_b1)
            rb_arr.append(res_rb)
            p0_arr.append(res_p0)
            p1_arr.append(res_p1)
            rp_arr.append(res_rp)
            v50_arr.append(res_v50)
            vm_arr.append(res_vm)
            n_array.append(res_n)
            thres_arr.append(res_thres)
            p1_div_vm_arr.append(res_p1/res_vm)
            p1_div_v50_arr.append(res_p1/res_v50)
            tm_arr.append(res_tm)
            t200_arr.append(res_t200)
            tstart_arr.append(res_tstart)
            tstart_minus_t200.append(res_tstart-res_t200)
            tm_minus_tstart.append(res_tm-res_tstart)
            k=(res_vm-res_thres)/(res_tm-res_tstart)
            k_arr.append(k)
            r_arr.append(res_p1/k)
            vend_arr.append(res_vend)
            d_arr.append(res_d)
            dV_arr.append(res_vend-res_thres)


    b0_arr=np.array(b0_arr)
    b1_arr=np.array(b1_arr)
    p0_arr=np.array(p0_arr)
    p1_arr=np.array(p1_arr)
    rb_arr=np.array(rb_arr)
    rp_arr=np.array(rp_arr)
    v50_arr=np.array(v50_arr)
    vm_arr=np.array(vm_arr)
    n_array=np.array(n_array)
    thres_arr=np.array(thres_arr)
    p1_div_vm_arr=np.array(p1_div_vm_arr)
    p1_div_v50_arr=np.array(p1_div_v50_arr)
    tm_arr=np.array(tm_arr)
    t200_arr=np.array(t200_arr)
    tstart_arr=np.array(tstart_arr)
    tstart_minus_t200=np.array(tstart_minus_t200)
    tm_minus_tstart=np.array(tm_minus_tstart)
    k_arr=np.array(k_arr)
    r_arr=np.array(r_arr)
    vend_arr=np.array(vend_arr)
    d_arr=np.array(d_arr)
    dV_arr=np.array(dV_arr)
    
    arr_of_arr=[b0_arr,b1_arr,p0_arr,p1_arr,rp_arr,rb_arr,v50_arr,vm_arr,n_array,thres_arr,p1_div_vm_arr,p1_div_v50_arr,tm_arr,t200_arr,tstart_arr,tstart_minus_t200,tm_minus_tstart,k_arr,r_arr,vend_arr,d_arr,dV_arr]
    
    return_dist = arr_of_arr[cut_no]

    return return_dist


def cutting_dV(cutting_arr,title_list,x_list,name_list,num_val,res_dir,main_arr,good_waveforms):

    #print(f"Length of good waveforms is: {len(good_waveforms)}")
    #print(f"Length of cutting array is {len(cutting_arr)}")

    ROOT.gErrorIgnoreLevel = ROOT.kWarning
    ROOT.gStyle.SetOptStat("emrou")

    lowx = np.percentile(cutting_arr, 0.5)
    highx = np.percentile(cutting_arr, 99.5)

    marginx = 0.1 * (highx - lowx)

    xmin = lowx - marginx
    xmax = highx + marginx

    hb=ROOT.TH1F(f"{title_list[num_val]}",f"{title_list[num_val]};{x_list[num_val]};Counts",50,xmin,xmax)

    hb.SetFillColor(ROOT.kCyan)
    hb.SetLineColor(ROOT.kBlack)
    
    for xb in cutting_arr:
        hb.Fill(xb)

    hb.Fit("gaus","Q")
    fit = hb.GetFunction("gaus")

    #chi2 = fit.GetChisquare()
    #ndf = fit.GetNDF()

    #mean  = fit.GetParameter(1)
    #sigma = fit.GetParameter(2)
    
    cb = ROOT.TCanvas("cb", "cb", 800, 600)
    hb.Draw("HIST")

    ID_info = ROOT.TLatex()
    ID_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
    ID_info.SetTextSize(0.02)
    ID_info.DrawLatex(0.2, 0.8, f"ID:{ID}")
    #fit.Draw("same")
    
    N=2

    #upper=mean+N*sigma
    #lower=mean-N*sigma

    #line2sigplus = ROOT.TLine(mean+N*sigma, 0, mean+N*sigma, hb.GetMaximum())
    #line2sigplus.SetLineColor(ROOT.kGreen+2)
    #line2sigplus.SetLineWidth(2)
    #line2sigplus.Draw("same")
    
    line2sigminus = ROOT.TLine(50, 0, 50,hb.GetMaximum())
    line2sigminus.SetLineColor(ROOT.kGreen+2)
    line2sigminus.SetLineWidth(2)
    line2sigminus.Draw("same")
    
    latex = ROOT.TLatex()
    latex.SetNDC(True)  # normalized coordinates
    latex.SetTextSize(0.03)

    latex.DrawLatex(0.60, 0.85, f"cut = {50} mV")
    #latex.DrawLatex(0.60, 0.80, f"#mu = {mean:.3f}")
    #latex.DrawLatex(0.60, 0.75, f"#sigma = {sigma:.3f}")
    
    cb.Modified()
    cb.Update()
    
    cb.SaveAs(f"{path}/{directory}/{res_dir}/dists/{name_list[num_val]}.pdf")
    
    cut_low = [good_waveforms[iii] for iii, xxx in enumerate(cutting_arr)
               if xxx < 50]

    return cut_low


def cutting_d(cutting_arr,title_list,x_list,name_list,num_val,res_dir,main_arr,good_waveforms):

    #print(f"Length of good waveforms is: {len(good_waveforms)}")
    #print(f"Length of cutting array is {len(cutting_arr)}")

    ROOT.gErrorIgnoreLevel = ROOT.kWarning
    ROOT.gStyle.SetOptStat("emrou")

    lowx = np.percentile(cutting_arr, 3)
    highx = np.percentile(cutting_arr, 97)

    marginx = 0.1 * (highx - lowx)

    xmin = lowx - marginx
    xmax = highx + marginx

    hb=ROOT.TH1F(f"{title_list[num_val]}",f"{title_list[num_val]};{x_list[num_val]};Counts",35,xmin,xmax)

    hb.SetFillColor(ROOT.kCyan)
    hb.SetLineColor(ROOT.kBlack)
    
    for xb in cutting_arr:
        hb.Fill(xb)

    cb = ROOT.TCanvas("cb", "cb", 800, 600)
    hb.Draw("HIST")

    spectrum = ROOT.TSpectrum(1)

    npeaks = spectrum.Search(hb, 1, "", 0.1)

    positions = spectrum.GetPositionX()

    for i in range(npeaks):
        right_peak=positions[i]

    #max_bin = hb.GetMaximumBin()
    #peak_x = hb.GetXaxis().GetBinCenter(max_bin)
    
    peak_x=right_peak

    peak_bin = hb.FindBin(peak_x)

    low = hb.GetXaxis().GetBinLowEdge(peak_bin-5)
    high = hb.GetXaxis().GetBinUpEdge(peak_bin+5)

    #for i in range(peak_bin - 10, peak_bin + 11):
        #low = hb.GetXaxis().GetBinLowEdge(i)
        #high = hb.GetXaxis().GetBinUpEdge(i)
    
    fit = ROOT.TF1("gaus", "gaus",low,high)
    
    fit.SetParameters(0,peak_x,0)

    hb.Fit(fit, "S R Q")

    mean = fit.GetParameter(1)
    sigma = fit.GetParameter(2)

    #hb.Fit("gaus")
    #fit = hb.GetFunction("gaus")

    #chi2 = fit.GetChisquare()
    #ndf = fit.GetNDF()

    #mean  = fit.GetParameter(1)
    #sigma = fit.GetParameter(2)
    
    fit.Draw("same")
    
    N=3

    q = array('d', [0.95])   # 95th percentile
    x = array('d', [0.])

    hb.GetQuantiles(1, x, q)

    lim = mean+N*sigma
 
    #upper=mean+N*sigma
    #lower=mean-N*sigma

    #line2sigplus = ROOT.TLine(mean+N*sigma, 0, mean+N*sigma, hb.GetMaximum())
    #line2sigplus.SetLineColor(ROOT.kGreen+2)
    #line2sigplus.SetLineWidth(2)
    #line2sigplus.Draw("same")
    
    line2sigminus = ROOT.TLine(lim, 0, lim,hb.GetMaximum())
    line2sigminus.SetLineColor(ROOT.kGreen+2)
    line2sigminus.SetLineWidth(2)
    line2sigminus.Draw("same")
    
    latex = ROOT.TLatex()
    latex.SetNDC(True)  # normalized coordinates
    latex.SetTextSize(0.03)

    latex.DrawLatex(0.60, 0.85, f"cut = {lim:.0f}")
    #latex.DrawLatex(0.60, 0.80, f"#mu = {mean:.3f}")
    #latex.DrawLatex(0.60, 0.75, f"#sigma = {sigma:.3f}")

    ID_info = ROOT.TLatex()
    ID_info.SetNDC()  # use normalized coordinates (0–1 on the canvas)
    ID_info.SetTextSize(0.02)
    ID_info.DrawLatex(0.2, 0.8, f"ID:{ID}")
    
    cb.Modified()
    cb.Update()
    
    cb.SaveAs(f"{path}/{directory}/{res_dir}/dists/{name_list[num_val]}.pdf")
    
    cut_high = [good_waveforms[iii] for iii, xxx in enumerate(cutting_arr)
                if xxx > lim]

    return cut_high




#####################################################################################
#####################################################################################
#####################################################################################
#####################################################################################
#####################################################################################
#####################################################################################
#####################################################################################
#####################################################################################
#####################################################################################


good_waveforms=np.linspace(0,len(sensorB[1])-1,len(sensorB[1]))

titles=["b_{0} Distribution Uncut","b_{1} Distribution Uncut","p_{0} Distribution Uncut","p_{1} Distribution Uncut","R_{p} Distribution Uncut","R_{b} Distribution Uncut","V_{p} Distribution Uncut","V_{m} Distribution Uncut","N_{points} Distribution Uncut", "V_start Distribution Uncut","p_{1}/V_{m} Distribution","p_{1}/V_{p} Distribution","T_{m} Distribution","T_{200} Distribution","T_{start} Distribution","dT_{s200} Distribution","dT_{ms} Distribution","k Distribution (mV/s)","r Distribution","V_{end} Distribution Uncut","d Distribution","#DeltaV Distribution","dt Distribution"]

x_titles=["b_{0} Value (mV)","b_{1} Value (mV/s)","p_{0} Value (mV)","p_{1} Value (mV/ns)","R_{p}","R_{b}","V_{p} (mV)","V_{m} (mV)","N_{points}", "V_{start} (mV)","p_{1}/V_{m} (s)","p_{1}/V_{p} (s)","T_{m} (s)","T_{200} (s)","T_{start} (s)","dT_{s200} (s)","dT_{ms} (s)","k (mV/s)","r","V_{end} (mV)","d", "#DeltaV (mV)", "dt (~mu s)"]

names=["b0-dist","b1-dist","p0-dist","p1-dist","rp-dist","rb-dist","v50-dist","vm-dist","n-dist","thres-dist","p1vm-dist","p1v50-dist","tm-dist","t200-dist","tstart-dist","tsmint200-dist","tmmints-dist","k-dist","r-dist","vend-dist","d-dist","dV-dist","dt-dist"]

excluded=np.array([])

b1_arr = plotting(excluded,titles,x_titles,names,1,"uncut",good_waveforms)
#####B1 CUTTING#####################################################################
outliers_b1_low,outliers_b1_high = cutting(b1_arr,titles,x_titles,names,1,"uncut",sensorB,good_waveforms)

b1_count_low=0
b1_count_high=0

'''
for uu in range(len(sensorB[1])):
    if uu in outliers_b1_low: 
        waveform_drawing(sensorB,uu,b1_count_low,"b1-cutting/low")
        b1_count_low+=1

for uuu in range(len(sensorB[1])):
    if uuu in outliers_b1_high: 
        waveform_drawing(sensorB,uuu,b1_count_high,"b1-cutting/high")
        b1_count_high+=1
'''
excluded_b1 = set(outliers_b1_low) | set(outliers_b1_high)

#print(f"b1 excluded = {len(excluded_b1)}")

good_waveforms = good_waveforms[
    ~np.isin(good_waveforms, list(excluded_b1))
]

#print(f"Good waveforms remaining: {len(good_waveforms)}")

####DRAW REJECTED WAVEFORMS#################################

b1_count=0

titles_b1=["b_{0} Distribution Post b_{1} Cut","b_{1} Distribution Post b_{1} Cut","p_{0} Distribution Post b_{1} Cut","p_{1} Distribution Post b_{1} Cut","R_{p} Distribution Post b_{1} Cut","R_{b} Distribution Post b_{1} Cut","V_{p} Distribution Post b_{1} Cut","V_{m} Distribution Post b_{1} Cut","N_{points} Distribution Post b_{1} Cut","V_{start} Distribution Post b_{1} Cut","p_{1}/V_{m} Distribution Post b_{1} Cut","p_{1}/V_{p} Distribution Post b_{1} Cut","T_{m} Distribution Post b_{1} Cut","T_{200} Distribution Post b_{1} Cut","T_{start} Distribution Post b_{1} Cut","dT_{s200} Distribution Post b_{1} Cut","dT_{ms} Distribution Post b_{1} Cut","k Distribution Post b_{1} Cut","r Distribution Post b_{1} Cut","V_{end} Distribution Post b_{1} Cut","d Distribution Post b_{1} Cut","#DeltaV Distribution Post b_{1} Cut", "dt (~mu s)"]

b0_arr = plotting(excluded,titles_b1,x_titles,names,0,"b1-cutting",good_waveforms)

outliers_b0_low, outliers_b0_high = cutting(b0_arr,titles_b1,x_titles,names,0,"b1-cutting",sensorB,good_waveforms)

b0_count_low=0
b0_count_high=0
'''
for vv in range(len(sensorB[1])):
    if vv in outliers_b0_low: 
        waveform_drawing(sensorB,vv,b0_count_low,"b0-cutting/low")
        b0_count_low+=1

for vvv in range(len(sensorB[1])):
    if vvv in outliers_b0_high: 
        waveform_drawing(sensorB,vvv,b0_count_high,"b0-cutting/high")
        b0_count_high+=1
'''

excluded_b0 = set(outliers_b0_low) | set(outliers_b0_high)

#print(f"b0 excluded = {len(excluded_b0)}")

good_waveforms = good_waveforms[
    ~np.isin(good_waveforms, list(excluded_b0))
]

#print(f"Good waveforms remaining: {len(good_waveforms)}")

titles_b0=["b_{0} Distribution Post b_{1} b_{0} Cut","b_{1} Distribution Post b_{1} b_{0} Cut","p_{0} Distribution Post b_{1} b_{0} Cut","p_{1} Distribution Post b_{1} b_{0} Cut","R_{p} Distribution Post b_{1} b_{0} Cut","R_{b} Distribution Post b_{1} b_{0} Cut","V_{p} Distribution Post b_{1} b_{0} Cut","V_{m} Distribution Post b_{1} b_{0} Cut","N_{point} Distribution Post b_{1} b_{0} Cut","V_{start} Distribution Post b_{1} b_{0} Cut","p_{1}/V_{m} Distribution Post b_{1} b_{0} Cut","p_{1}/V_{p} Distribution Post b_{1} b_{0} Cut","T_{m} Distribution Post b_{1} b_{0} Cut","T_{200} Distribution Post b_{1} b_{0} Cut","T_{start} Distribution Post b_{1} b_{0} Cut","dT_{s200} Distribution Post b_{1} b_{0} Cut","dT_{ms} Distribution Post b_{1} b_{0} Cut","k Distribution Post b_{1} b_{0} Cut","r Distribution Post b_{1} b_{0} Cut","V_{end} Distribution Post b_{1} b_{0} Cut","d Distribution Post b_{1} b_{0} Cut","#DeltaV Distribution Post b_{1} b_{0} Cut", "dt (~mu s)"]

b1_count=0

#titles_b1=["b_{0} Distribution Post b_{1} Cut","b_{1} Distribution Post b_{1} Cut","p_{0} Distribution Post b_{1} Cut","p_{1} Distribution Post b_{1} Cut","R_{p} Distribution Post b_{1} Cut","R_{b} Distribution Post b_{1} Cut","V_{p} Distribution Post b_{1} Cut","V_{m} Distribution Post b_{1} Cut","N_{points} Distribution Post b_{1} Cut","V_{start} Distribution Post b_{1} Cut","p_{1}/V_{m} Distribution Post b_{1} Cut","p_{1}/V_{p} Distribution Post b_{1} Cut","T_{m} Distribution Post b_{1} Cut","T_{200} Distribution Post b_{1} Cut","T_{start} Distribution Post b_{1} Cut","dT_{s200} Distribution Post b_{1} Cut","dT_{ms} Distribution Post b_{1} Cut","k Distribution Post b_{1} Cut","r Distribution Post b_{1} Cut","V_{end} Distribution Post b_{1} Cut","d Distribution Post b_{1} Cut","#DeltaV Distribution Post b_{1} Cut"]

dV_arr = plotting(excluded,titles_b0,x_titles,names,21,"b0-cutting",good_waveforms)

outliers_dV = cutting_dV(dV_arr,titles_b0,x_titles,names,21,"b0-cutting",sensorB,good_waveforms)

dV_count_low=0

'''
for aa in range(len(sensorB[1])):
    if aa in outliers_dV: 
        waveform_drawing(sensorB,aa,dV_count_low,"vend-cutting/low")
        dV_count_low+=1
'''


excluded_dV = set(outliers_dV)

#print(f"dV excluded = {len(excluded_dV)}")

good_waveforms = good_waveforms[
    ~np.isin(good_waveforms, list(excluded_dV))
]

#print(f"Good waveforms remaining: {len(good_waveforms)}")


#print(f"vend excluded = {len(outliers_dV)}")

'''
vm_arr=get_dist(7,"test",good_waveforms)

outliers_r_low, outliers_r_high = cutting_r(r_arr,titles_b0,x_titles,names,18,"b0-cutting",sensorB,good_waveforms,vm_arr)

r_count_low=0
r_count_high=0

for zz in range(len(sensorB[1])):
    if zz in outliers_r_low: 
        waveform_drawing(sensorB,zz,r_count_low,"r-cutting/low")
        r_count_low+=1

for zzz in range(len(sensorB[1])):
    if zzz in outliers_r_high: 
        waveform_drawing(sensorB,zzz,r_count_high,"r-cutting/high")
        r_count_high+=1

excluded_r = set(outliers_r_low) | set(outliers_r_high)

print(f"r excluded = {len(excluded_r)}")

good_waveforms = good_waveforms[
    ~np.isin(good_waveforms, list(excluded_r))
]

print(f"Good waveforms remaining: {len(good_waveforms)}")
        
titles_r=["b_{0} Distribution Post b_{1} b_{0} r Cut","b_{1} Distribution Post b_{1} b_{0} r Cut","p_{0} Distribution Post b_{1} b_{0} r Cut","p_{1} Distribution Post b_{1} b_{0} r Cut","R_{p} Distribution Post b_{1} b_{0} r Cut","R_{b} Distribution Post b_{1} b_{0} r Cut","V_{p} Distribution Post b_{1} b_{0} r Cut","V_{m} Distribution Post b_{1} b_{0} r Cut","N_{point} Distribution Post b_{1} b_{0} r Cut","V_{start} Distribution Post b_{1} b_{0} r Cut","p_{1}/V_{m} Distribution Post b_{1} b_{0} r Cut","p_{1}/V_{p} Distribution Post b_{1} b_{0} r Cut","T_{m} Distribution Post b_{1} b_{0} r Cut","T_{200} Distribution Post b_{1} b_{0} r Cut","T_{start} Distribution Post b_{1} b_{0} r Cut","dT_{s200} Distribution Post b_{1} b_{0} r Cut","dT_{ms} Distribution Post b_{1} b_{0} r Cut","k Distribution Post b_{1} b_{0} r Cut","r Distribution Post b_{1} b_{0} r Cut","V_{end} Distribution Post b_{1} b_{0} r Cut","d Distribution Post b_{1} b_{0} r Cut"]
'''
titles_vend=["b_{0} Distribution Post b_{1} b_{0} #DeltaV Cut","b_{1} Distribution Post b_{1} b_{0} #DeltaV Cut","p_{0} Distribution Post b_{1} b_{0} #DeltaV Cut","p_{1} Distribution Post b_{1} b_{0} #DeltaV Cut","R_{p} Distribution Post b_{1} b_{0} #DeltaV Cut","R_{b} Distribution Post b_{1} b_{0} #DeltaV Cut","V_{p} Distribution Post b_{1} b_{0} #DeltaV Cut","V_{m} Distribution Post b_{1} b_{0} #DeltaV Cut","N_{point} Distribution Post b_{1} b_{0} #DeltaV Cut","V_{start} Distribution Post b_{1} b_{0} #DeltaV Cut","p_{1}/V_{m} Distribution Post b_{1} b_{0} #DeltaV Cut","p_{1}/V_{p} Distribution Post b_{1} b_{0} #DeltaV Cut","T_{m} Distribution Post b_{1} b_{0} #DeltaV Cut","T_{200} Distribution Post b_{1} b_{0} #DeltaV Cut","T_{start} Distribution Post b_{1} b_{0} #DeltaV Cut","dT_{s200} Distribution Post b_{1} b_{0} #DeltaV Cut","dT_{ms} Distribution Post b_{1} b_{0} #DeltaV Cut","k Distribution Post b_{1} b_{0} #DeltaV Cut","r Distribution Post b_{1} b_{0} #DeltaV Cut","V_{end} Distribution Post b_{1} b_{0} #DeltaV Cut","d Distribution Post b_{1} b_{0} #DeltaV Cut","#DeltaV Distribution Post b_{1} b_{0} #DeltaV Cut", "dt (~mu s)"]


d_arr = plotting(excluded,titles_vend,x_titles,names,20,"vend-cutting",good_waveforms)

outliers_d_high = cutting_d(d_arr,titles_vend,x_titles,names,20,"vend-cutting",sensorB,good_waveforms)

d_count_high=0
'''
for ddd in range(len(sensorB[1])):
    if ddd in outliers_d_high: 
        waveform_drawing(sensorB,ddd,d_count_high,"d-cutting/high")
        #print(b1_count)
        d_count_high+=1
'''
#excluded = set(excluded) | set(outliers_dts200_low) 
excluded_d = set(outliers_d_high)

good_waveforms = good_waveforms[
    ~np.isin(good_waveforms, list(excluded_d))
]
'''
tm_count=0

titles_vend=["b_{0} Distribution Post b_{1} b_{0} V_{end} Cut","b_{1} Distribution Post b_{1} b_{0} V_{end} Cut","p_{0} Distribution Post b_{1} b_{0} V_{end} Cut","p_{1} Distribution Post b_{1} b_{0} V_{end} Cut","R_{p} Distribution Post b_{1} b_{0} V_{end} Cut","R_{b} Distribution Post b_{1} b_{0} V_{end} Cut","V_{p} Distribution Post b_{1} b_{0} V_{end} Cut","V_{m} Distribution Post b_{1} b_{0} V_{end} Cut","N_{point} Distribution Post b_{1} b_{0} V_{end} Cut","V_{start} Distribution Post b_{1} b_{0} V_{end} Cut","p_{1}/V_{m} Distribution Post b_{1} b_{0} V_{end} Cut","p_{1}/V_{p} Distribution Post b_{1} b_{0} V_{end} Cut","T_{m} Distribution Post b_{1} b_{0} V_{end} Cut","T_{200} Distribution Post b_{1} b_{0} V_{end} Cut","T_{start} Distribution Post b_{1} b_{0} V_{end} Cut","dT_{s200} Distribution Post b_{1} b_{0} V_{end} Cut","dT_{ms} Distribution Post b_{1} b_{0} V_{end} Cut","k Distribution Post b_{1} b_{0} r d Cut","r Distribution Post b_{1} b_{0} r d Cut","V_{end} Distribution Post b_{1} b_{0} r d Cut","d Distribution Post b_{1} b_{0} r d Cut","#DeltaV Distribution Post b_{1} b_{0} r d Cut"]
'''
titles_d=["b_{0} Distribution Post b_{1} b_{0} #DeltaV d Cut","b_{1} Distribution Post b_{1} b_{0} #DeltaV d Cut","p_{0} Distribution Post b_{1} b_{0} #DeltaV d Cut","p_{1} Distribution Post b_{1} b_{0} #DeltaV d Cut","R_{p} Distribution Post b_{1} b_{0} #DeltaV d Cut","R_{b} Distribution Post b_{1} b_{0} #DeltaV d Cut","V_{p} Distribution Post b_{1} b_{0} #DeltaV d Cut","V_{m} Distribution Post b_{1} b_{0} #DeltaV d Cut","N_{point} Distribution Post b_{1} b_{0} #DeltaV d Cut","V_{start} Distribution Post b_{1} b_{0} #DeltaV d Cut","p_{1}/V_{m} Distribution Post b_{1} b_{0} #DeltaV d Cut","p_{1}/V_{p} Distribution Post b_{1} b_{0} #DeltaV d Cut","T_{m} Distribution Post b_{1} b_{0} #DeltaV d Cut","T_{200} Distribution Post b_{1} b_{0} #DeltaV d Cut","T_{start} Distribution Post b_{1} b_{0} #DeltaV d Cut","dT_{s200} Distribution Post b_{1} b_{0} #DeltaV d Cut","dT_{ms} Distribution Post b_{1} b_{0} #DeltaV d Cut","k Distribution Post b_{1} b_{0} #DeltaV d Cut","r Distribution Post b_{1} b_{0} #DeltaV d Cut","V_{end} Distribution Post b_{1} b_{0} #DeltaV d Cut","d Distribution Post b_{1} b_{0} #DeltaV d Cut","d Distribution Post b_{1} b_{0} #DeltaV d Cut", "dt (~mu s)"]

b0_arr = plotting(excluded,titles_d,x_titles,names,0,"d-cutting",good_waveforms)

#print("Done")


b0 = array('d', [0])
b1 = array('d', [0])
p0 = array('d', [0])
p1 = array('d', [0])
rp = array('d', [0])
rb = array('d', [0])
vm = array('d', [0])
v50 = array('d', [0])
tm = array('d', [0])
tstart = array('d', [0])
t200 = array('d', [0])
npoints= array('d', [0])
thres= array('d', [0])
p1DivVm= array('d', [0])
p1DivV50= array('d', [0])
dt_s200=array('d', [0])
dt_ms=array('d', [0])
k=array('d', [0])
r=array('d', [0])
vend=array('d', [0])
wave_num=array('d', [0])
d=array('d',[0])
dV=array('d',[0])

bl_vec = ROOT.std.vector('double')()
time_vec = ROOT.std.vector('double')()
wf_raw   = ROOT.std.vector('double')()

f = ROOT.TFile(f"{path}/{directory}/waveforms.root", "RECREATE")

t_b1 = ROOT.TTree("b1_rejected", "Rejected b1 waveforms")
t_b0 = ROOT.TTree("b0_rejected", "Rejected b0 waveforms")
t_dV = ROOT.TTree("dV_rejected",  "Rejected dV waveforms")
t_d = ROOT.TTree("d_rejected",  "Rejected d waveforms")
t_good = ROOT.TTree("good", "Good waveforms")

t_b1.Branch("time", time_vec)
t_b1.Branch("waveform", bl_vec)
t_b1.Branch("raw_waveform", wf_raw)
t_b1.Branch("b0", b0, "b0/D")
t_b1.Branch("b1", b1, "b1/D")
t_b1.Branch("p0", p0, "p0/D")
t_b1.Branch("p1", p1, "p1/D")
t_b1.Branch("rb", rb, "rb/D")
t_b1.Branch("rp", rp, "rp/D")
t_b1.Branch("v50", v50, "v50/D")
t_b1.Branch("npoints", npoints, "npoints/D")
t_b1.Branch("thres", thres, "thres/D")
t_b1.Branch("p1DivVm", p1DivVm, "p1DivVm/D")
t_b1.Branch("p1DivV50", p1DivV50, "p1DivV50/D")
t_b1.Branch("tm", tm, "tm/D")
t_b1.Branch("tstart", tstart, "tstart/D")
t_b1.Branch("t200", t200, "t200/D")
t_b1.Branch("dt_s200", dt_s200, "dt_s200/D")
t_b1.Branch("dt_ms", dt_ms, "dt_ms/D")
t_b1.Branch("k", k, "k_arr/D")
t_b1.Branch("r", r, "r_arr/D")
t_b1.Branch("vend", vend, "vend_arr/D")
t_b1.Branch("wave_num",wave_num,"wave_num/D")
t_b1.Branch("d",d,"d/D")
t_b1.Branch("dV",dV,"dV/D")


t_b0.Branch("time", time_vec)
t_b0.Branch("waveform", bl_vec)
t_b0.Branch("raw_waveform", wf_raw)
t_b0.Branch("b0", b0, "b0/D")
t_b0.Branch("b1", b1, "b1/D")
t_b0.Branch("p0", p0, "p0/D")
t_b0.Branch("p1", p1, "p1/D")
t_b0.Branch("rb", rb, "rb/D")
t_b0.Branch("rp", rp, "rp/D")
t_b0.Branch("v50", v50, "v50/D")
t_b0.Branch("vm", vm, "vm/D")
t_b0.Branch("npoints", npoints, "npoints/D")
t_b0.Branch("thres", thres, "thres/D")
t_b0.Branch("p1DivVm", p1DivVm, "p1DivVm/D")
t_b0.Branch("p1DivV50", p1DivV50, "p1DivV50/D")
t_b0.Branch("tm", tm, "tm/D")
t_b0.Branch("tstart", tstart, "tstart/D")
t_b0.Branch("t200", t200, "t200/D")
t_b0.Branch("dt_s200", dt_s200, "dt_s200/D")
t_b0.Branch("dt_ms", dt_ms, "dt_ms/D")
t_b0.Branch("k", k, "k_arr/D")
t_b0.Branch("r", r, "r_arr/D")
t_b0.Branch("vend", vend, "vend_arr/D")
t_b0.Branch("wave_num",wave_num,"wave_num/D")
t_b0.Branch("d",d,"d/D")
t_b0.Branch("dV",dV,"dV/D")

t_dV.Branch("time", time_vec)
t_dV.Branch("waveform", bl_vec)
t_dV.Branch("raw_waveform", wf_raw)
t_dV.Branch("b0", b0, "b0/D")
t_dV.Branch("b1", b1, "b1/D")
t_dV.Branch("p0", p0, "p0/D")
t_dV.Branch("p1", p1, "p1/D")
t_dV.Branch("rb", rb, "rb/D")
t_dV.Branch("rp", rp, "rp/D")
t_dV.Branch("v50", v50, "v50/D")
t_dV.Branch("vm", vm, "vm/D")
t_dV.Branch("npoints", npoints, "npoints/D")
t_dV.Branch("thres", thres, "thres/D")
t_dV.Branch("p1DivVm", p1DivVm, "p1DivVm/D")
t_dV.Branch("p1DivV50", p1DivV50, "p1DivV50/D")
t_dV.Branch("tm", tm, "tm/D")
t_dV.Branch("tstart", tstart, "tstart/D")
t_dV.Branch("t200", t200, "t200/D")
t_dV.Branch("dt_s200", dt_s200, "dt_s200/D")
t_dV.Branch("dt_ms", dt_ms, "dt_ms/D")
t_dV.Branch("k", k, "k_arr/D")
t_dV.Branch("r", r, "r_arr/D")
t_dV.Branch("vend", vend, "vend_arr/D")
t_dV.Branch("wave_num",wave_num,"wave_num/D")
t_dV.Branch("d",d,"d/D")
t_dV.Branch("dV",dV,"dV/D")

t_good.Branch("time", time_vec)
t_good.Branch("waveform", bl_vec)
t_good.Branch("raw_waveform", wf_raw)
t_good.Branch("b0", b0, "b0/D")
t_good.Branch("b1", b1, "b1/D")
t_good.Branch("p0", p0, "p0/D")
t_good.Branch("p1", p1, "p1/D")
t_good.Branch("rb", rb, "rb/D")
t_good.Branch("rp", rp, "rp/D")
t_good.Branch("v50", v50, "v50/D")
t_good.Branch("vm", vm, "vm/D")
t_good.Branch("npoints", npoints, "npoints/D")
t_good.Branch("thres", thres, "thres/D")
t_good.Branch("p1DivVm", p1DivVm, "p1DivVm/D")
t_good.Branch("p1DivV50", p1DivV50, "p1DivV50/D")
t_good.Branch("tm", tm, "tm/D")
t_good.Branch("tstart", tstart, "tstart/D")
t_good.Branch("t200", t200, "t200/D")
t_good.Branch("dt_s200", dt_s200, "dt_s200/D")
t_good.Branch("dt_ms", dt_ms, "dt_ms/D")
t_good.Branch("k", k, "k/D")
t_good.Branch("r", r, "r/D")
t_good.Branch("vend", vend, "vend_arr/D")
t_good.Branch("wave_num",wave_num,"wave_num/D")
t_good.Branch("d",d,"d/D")
t_good.Branch("dV",dV,"dV/D")

numbers_root = [10000000000000,200000000000000000]

for oo in range (sensorB.shape[1]):
    
    time_vec.clear()
    wf_raw.clear()
    bl_vec.clear()
    #if oo not in excluded:
    res_b0, res_b1, res_rb, res_p0, res_p1, res_rp, res_v50, res_vm, res_n, res_thres, res_tm, res_t200, res_tstart, res_vend, res_d, res_dt = waveform_analysis(sensorB,oo,numbers_root,"test/cut-waveforms-2sig")
    
    for ttt, yyy in zip(time_x, sensorB[:,oo]):
        time_vec.push_back(float(ttt))
        wf_raw.push_back(float(yyy))
        bl_vec.push_back(float(yyy - res_b0))

    b0[0] = res_b0
    b1[0] = res_b1
    p0[0] = res_p0
    p1[0] = res_p1
    rb[0] = res_rb
    rp[0] = res_rp
    v50[0] = res_v50
    vm[0] = res_vm
    npoints[0]= res_n
    thres[0]=res_thres
    p1DivVm[0]=res_p1/res_vm
    p1DivV50[0]=res_p1/res_v50
    tm[0] = res_tm
    tstart[0] = res_tstart
    t200[0] = res_t200
    dt_s200[0] = res_tstart-res_t200
    dt_ms[0] = res_tm-res_tstart
    k_val=(res_vm-res_thres)/(res_tm-res_tstart)
    k[0] = k_val
    r[0] = (res_p1/k_val)
    vend[0] = res_vend
    wave_num[0] = oo
    d[0] = res_d
    '''
    if oo in excluded_b1:
        t_b1.Fill()
        
    elif oo in excluded_b0:
        t_b0.Fill()
    elif oo in excluded_dV:
        t_dV.Fill()
    elif oo in excluded_d:
        t_d.Fill()
    else:
        t_good.Fill()
    '''
    if oo not in (excluded_b1 and excluded_b0 and excluded_dV and excluded_d):
        t_b0.Fill()
    else:
        t_good.Fill()
    

f.cd()

t_b1.Write()
t_b0.Write()
t_dV.Write()
t_d.Write()
t_good.Write()

f.Close()

if os.path.exists("Distributions_uncut.root"):
    os.remove("Distributions_uncut.root")


