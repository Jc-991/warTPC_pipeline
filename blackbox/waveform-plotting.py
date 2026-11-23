import numpy as np
import matplotlib.pyplot as plt
import ROOT
import sys
import pandas as pd
import random
from array import array
import random
import shutil
import os
import math
from datetime import datetime, timedelta
import csv
ROOT.gErrorIgnoreLevel = ROOT.kWarning
ROOT.gROOT.SetBatch(True)


thresholdp1=0

thresholdv50=0

latex = ROOT.TLatex()
latex.SetNDC(True)  # normalized coordinates
latex.SetTextSize(0.03)

def NormalizeXSlices(hist2d):
    h_norm = hist2d.Clone(hist2d.GetName() + "_norm")
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

filename="waveforms.root"
path=str(sys.argv[1])
directory=str(sys.argv[2])

thresholdp1=0.0

cut=True

with open(f"{path}/{directory}/settings.csv", "r") as f:
    reader = csv.reader(f)

    for row in reader:
        ID=str(row[0])
        pres=float(row[1])
        FC=float(row[2])
        E1=float(row[3])
        E2=float(row[4])
        E3=float(row[5])
        E4=float(row[6])
        purity=float(row[7])

div=2

shutil.rmtree(f"{path}/{directory}/p1", ignore_errors=True)
os.makedirs(f"{path}/{directory}/p1", exist_ok=True)

f = ROOT.TFile(f"{path}/{directory}/{filename}")

tree =f.Get("good")

entries=tree.GetEntries()

count=0

all_chi=[]

values = []
uncut_values=[]


for event_uncut in tree:
        uncut_values.append(event_uncut.p1)

uncut_values = np.array(uncut_values)

lowx = np.percentile(uncut_values, 0.5)
highx = np.percentile(uncut_values, 99.5)

marginx = 0.1 * (highx - lowx)

xmin = lowx - marginx
xmax = highx + marginx

h1uncut = ROOT.TH1D(
    "h1uncut",
    "p1 Full Distribution; p1; Counts",
    100,     # number of bins
    xmin,     # minimum
    xmax       # maximum
)

h1uncut.SetLineColor(ROOT.kBlack)
h1uncut.SetFillColor(ROOT.kCyan)

for xuncut in uncut_values:
        h1uncut.Fill(xuncut)

cuncut=ROOT.TCanvas("cuncut","cuncut",800,600)

h1uncut.Draw("HIST")

if cut == True:

    spectrum = ROOT.TSpectrum(2)  # expect up to 2 peaks

    npeaks = spectrum.Search(h1uncut, 5, "", 0.01)

    positions = spectrum.GetPositionX()
   
    thresholdp1=np.abs(positions[1]-positions[0])/div


linecut = ROOT.TLine(thresholdp1, 0, thresholdp1,h1uncut.GetMaximum())
linecut.SetLineColor(ROOT.kPink)
linecut.SetLineWidth(2)
linecut.Draw("same")

cuncut.Modified()
cuncut.Update()

latex_ID = ROOT.TLatex()
latex_ID.SetNDC()
latex_ID.SetTextSize(0.03)
latex_ID.DrawLatex(0.15, 0.85, f"ID: {ID}")

cuncut.SaveAs(f"{path}/{directory}/p1/p1-clean.png")
cuncut.SaveAs(f"{path}/{directory}/p1/p1-clean.eps")

#norm=1

for event in tree:
    if event.p1 > thresholdp1:
        values.append(event.p1)

values = np.array(values)

lowx = np.percentile(values, 0.5)
highx = np.percentile(values, 99.5)

marginx = 0.1 * (highx - lowx)

xmin = lowx - marginx
xmax = highx + marginx

h1 = ROOT.TH1D(
    "h1",
    "p1 Distribution Fitting Range; p1; Counts",
    100,     # number of bins
    xmin,     # minimum
    xmax       # maximum
)

h1.SetLineColor(ROOT.kBlack)
h1.SetFillColor(ROOT.kCyan)

for xb in values:
        h1.Fill(xb)

fit = ROOT.TF1("mygaus", "gaus", min(values), max(values))

fit.SetParameters(
    0.0,  # amplitude
    1.6,             # mean
    0.0               # sigma
)

h1.Fit(fit, "S R Q")           # refit using the updated starting values

c=ROOT.TCanvas("c","c",800,600)

chi2 = fit.GetChisquare()
ndf = fit.GetNDF()

mean  = fit.GetParameter(1)
sigma = fit.GetParameter(2)

h1.Draw("HIST")



latex.DrawLatex(0.60, 0.85, f"#chi^{{2}}/NDF = {chi2:.1f}/{ndf}")
latex.DrawLatex(0.60, 0.80, f"#mu = {mean:.3f}")
latex.DrawLatex(0.60, 0.75, f"#sigma = {sigma:.3f}")

line2sigplus = ROOT.TLine(mean+2*sigma, 0, mean+2*sigma, h1.GetMaximum())
line2sigplus.SetLineColor(ROOT.kGreen)
line2sigplus.SetLineWidth(2)
line2sigplus.Draw("same")
    
line2sigminus = ROOT.TLine(mean-2*sigma, 0, mean-2*sigma,h1.GetMaximum())
line2sigminus.SetLineColor(ROOT.kGreen)
line2sigminus.SetLineWidth(2)
line2sigminus.Draw("same")

line5sigplus = ROOT.TLine(mean+5*sigma, 0, mean+5*sigma, h1.GetMaximum())
line5sigplus.SetLineColor(ROOT.kBlue)
line5sigplus.SetLineWidth(2)
line5sigplus.Draw("same")
    
line5sigminus = ROOT.TLine(mean-5*sigma, 0, mean-5*sigma,h1.GetMaximum())
line5sigminus.SetLineColor(ROOT.kBlue)
line5sigminus.SetLineWidth(2)
line5sigminus.Draw("same")

line4sigplus = ROOT.TLine(mean+4*sigma, 0, mean+4*sigma, h1.GetMaximum())
line4sigplus.SetLineColor(ROOT.kRed)
line4sigplus.SetLineWidth(2)
line4sigplus.Draw("same")
    
line4sigminus = ROOT.TLine(mean-4*sigma, 0, mean-4*sigma,h1.GetMaximum())
line4sigminus.SetLineColor(ROOT.kRed)
line4sigminus.SetLineWidth(2)
line4sigminus.Draw("same")

line3sigplus = ROOT.TLine(mean+3*sigma, 0, mean+3*sigma, h1.GetMaximum())
line3sigplus.SetLineColor(ROOT.kPink)
line3sigplus.SetLineWidth(2)
line3sigplus.Draw("same")
    
line3sigminus = ROOT.TLine(mean-3*sigma, 0, mean-3*sigma,h1.GetMaximum())
line3sigminus.SetLineColor(ROOT.kPink)
line3sigminus.SetLineWidth(2)
line3sigminus.Draw("same")

fit.Draw("same")

latex_ID = ROOT.TLatex()
latex_ID.SetNDC()
latex_ID.SetTextSize(0.03)
latex_ID.DrawLatex(0.15, 0.85, f"ID: {ID}")

c.Modified()
c.Update()

c.SaveAs(f"{path}/{directory}/p1/p1-clean-cut.png")
c.SaveAs(f"{path}/{directory}/p1/p1-clean-cut.eps")


def signal_analysis(poly_type,sideband_limits,lim_num,cutoff):

    old = ROOT.gDirectory.FindObject("hfull")
    if old:
       old.Delete()

    side_band=[]
    full=[]

    for event in tree:
        if event.p1 > cutoff:
            full.append(event.p1)
            if ((mean-lim_num*sigma)  < event.p1 < (mean+lim_num*sigma)):
                if not ((mean-2*sigma)  < event.p1 < (mean+2*sigma)):
                    side_band.append(event.p1)



    side_band = np.array(side_band)

    full=np.array(full)
    
    minimum=min(side_band)
    maximum=max(side_band)

    tbkg=ROOT.TGraphErrors()
    tbkg.SetMarkerColor(ROOT.kBlue)
    tbkg.SetMarkerStyle(8)

    
    tfull=ROOT.TGraphErrors()
    tfull.SetMarkerColor(ROOT.kRed)
    tfull.SetMarkerStyle(8)
    
    hbkg = ROOT.TH1D(
        f"hbkg{poly_type} {sideband_limits}",
        f"p1 Sidebands {poly_type} {sideband_limits}; p1; Counts",
        100,     # number of bins
        xmin,     # minimum
        xmax       # maximum
    )

    hbkg.Reset()

    hfull = ROOT.TH1D(
        f"hfull",
        f"p1 Sidebands {poly_type} {sideband_limits}; p1; Counts",
        100,     # number of bins
        xmin,     # minimum
        xmax       # maximum
    )

    hfull.Reset()

    for xbkg in side_band:
        hbkg.Fill(xbkg)

    for xfull in full:
        hfull.Fill(xfull)
    
    n = 0
    for ll in range(1, hbkg.GetNbinsX() + 1):
        y = hbkg.GetBinContent(ll)
        x = hbkg.GetBinCenter(ll)
        ey = hbkg.GetBinError(ll)
        if y == 0:
            continue

        tbkg.SetPoint(n, x, y)
        tbkg.SetPointError(n, 0, ey)
        n += 1


        
    n = 0
    for ll in range(1, hfull.GetNbinsX() + 1):
        y = hfull.GetBinContent(ll)
        x = hfull.GetBinCenter(ll)
        ey = hfull.GetBinError(ll)
        tfull.SetPoint(n, x, y)
        tfull.SetPointError(n, 0, ey)
        n += 1

    
    hbkg.SetLineColor(ROOT.kBlack)
    hbkg.SetFillColor(ROOT.kCyan)
    
    val=10.0E-10
    if poly_type == "poly2":
        poly_fit = ROOT.TF1("poly_fit", "[0]+[1]*x+[2]*pow(x,2)",minimum,maximum)
        eq = f"y = p_{{0}}+p_{{1}}x+p_{{2}}x^{{2}}"
        #poly_fit.SetParameters(54, -1, -21)
    elif poly_type == "poly3":
        poly_fit = ROOT.TF1("poly_fit", "[0]+[1]*x+[2]*pow(x,2)+[3]*pow(x,3)",minimum,maximum)
        eq = f"y = p_{{0}}+p_{{1}}x+p_{{2}}x^2+p_{{3}}x^{{3}}"
        #poly_fit.SetParameters(30, 120, -160, 50)
    elif poly_type == "poly4":
        poly_fit = ROOT.TF1("poly_fit", "[0]+[1]*x+[2]*pow(x,2)+[3]*pow(x,3)+[4]*pow(x,4)",minimum,maximum)
        eq = f"y = p_{{0}}+p_{{1}}x+p_{{2}}x^2+p_{{3}}x^{{3}}+p_{{4}}x^{{4}}"
        #poly_fit.SetParameters(70, -170, 420, -400, 120)
    else:
        print("Poly type error")

    poly_fit.SetLineColor(ROOT.kBlue)
    
    tbkg.Fit(poly_fit, "S R Q")
    
    tfull.SetTitle(f"p1 Sidebands {poly_type} {sideband_limits}; p1 (mV/ns); Counts")
    tbkg.SetMarkerStyle(21)
    tbkg.SetMarkerSize(1)
    
    cbkg=ROOT.TCanvas(f"cbkg{poly_type} {sideband_limits}",f"cbkg{poly_type} {sideband_limits}",800,600)

    tfull.Draw("APE")
    tbkg.Draw("PE")
    poly_fit.Draw("same")

    cbkg.Modified()
    cbkg.Update()

    chi2_poly=poly_fit.GetChisquare()
    ndf_poly=poly_fit.GetNDF()

    latex.DrawLatex(0.60, 0.70, f"#Chi2/NDF = {chi2_poly:.2f}/{ndf_poly}")
    latex.DrawLatex(0.60, 0.65, eq)

    if poly_type == "poly2":
        latex.DrawLatex(0.60, 0.60, f"p_{{0}} = {poly_fit.GetParameter(0):.2f}")
        latex.DrawLatex(0.60, 0.55, f"p_{{1}} = {poly_fit.GetParameter(1):.2f}")
        latex.DrawLatex(0.60, 0.50, f"p_{{2}} = {poly_fit.GetParameter(2):.2f}")
    elif poly_type == "poly3":
        latex.DrawLatex(0.60, 0.60, f"p_{{0}} = {poly_fit.GetParameter(0):.2f}")
        latex.DrawLatex(0.60, 0.55, f"p_{{1}} = {poly_fit.GetParameter(1):.2f}")
        latex.DrawLatex(0.60, 0.50, f"p_{{2}} = {poly_fit.GetParameter(2):.2f}")
        latex.DrawLatex(0.60, 0.45, f"p_{{3}} = {poly_fit.GetParameter(3):.2f}")
    elif poly_type == "poly4":
        latex.DrawLatex(0.60, 0.60, f"p_{{0}} = {poly_fit.GetParameter(0):.2f}")
        latex.DrawLatex(0.60, 0.55, f"p_{{1}} = {poly_fit.GetParameter(1):.2f}")
        latex.DrawLatex(0.60, 0.50, f"p_{{2}} = {poly_fit.GetParameter(2):.2f}")
        latex.DrawLatex(0.60, 0.45, f"p_{{3}} = {poly_fit.GetParameter(3):.2f}")
        latex.DrawLatex(0.60, 0.40, f"p_{{4}} = {poly_fit.GetParameter(4):.2f}")

    latex_ID = ROOT.TLatex()
    latex_ID.SetNDC()
    latex_ID.SetTextSize(0.03)
    latex_ID.DrawLatex(0.15, 0.85, f"ID: {ID}")
    
    cbkg.SaveAs(f"{path}/{directory}/p1/sidebands{poly_type}_{sideband_limits}.png")
    cbkg.SaveAs(f"{path}/{directory}/p1/sidebands{poly_type}_{sideband_limits}.eps")

    bkgsub = []

    for tt in range(1, h1.GetNbinsX() + 1):
        x = h1.GetBinCenter(tt)
        bkg_est=poly_fit.Eval(x)
        #if ((mean-2*sigma)  < h1.GetBinCenter(tt) < (mean+2*sigma)):
        if ((mean-lim_num*sigma)  < h1.GetBinCenter(tt) < (mean+lim_num*sigma)):
            bkgsub.append(h1.GetBinContent(tt)-bkg_est)
        else:
            bkgsub.append(0)


    bkgsub=np.array(bkgsub)

    hsub = ROOT.TH1D(
        f"hsub{poly_type} {sideband_limits}",
        f"p1 Background Subtracted {poly_type} {sideband_limits}; p1 (mV/ns); Counts",
        100,     # number of bins
        xmin,     # minimum
        xmax       # maximum
    )

    hsub.Reset()
    hsub.SetLineColor(ROOT.kBlack)
    hsub.SetFillColor(ROOT.kCyan)


    for rr in range(0, hsub.GetNbinsX()):
        hsub.SetBinContent(rr+1, bkgsub[rr])

    hsub.ResetStats()
        
    #sig_mean=hsub.GetMean()
    #sig_rms=hsub.GetRMS()
    
        
    csub=ROOT.TCanvas(f"csub{poly_type} {sideband_limits}",f"csub{poly_type} {sideband_limits}",800,600)

    hsub.Fit(fit, "S R Q")

    sig_chi2 = fit.GetChisquare()
    sig_ndf = fit.GetNDF()

    sig_mean  = fit.GetParameter(1)
    sig_rms = fit.GetParameter(2)

    hsub.Draw("HIST")
    fit.Draw("same")

    latex.DrawLatex(0.60, 0.80, f"#mu = {sig_mean:.2f}")
    latex.DrawLatex(0.60, 0.75, f"#sigma = {sig_rms:.2f}")
    latex.DrawLatex(0.60, 0.70, f"#Chi2/ndf = {sig_chi2:.2f}/{sig_ndf:.2f}")
    
    csub.Modified()
    csub.Update()

    latex_ID = ROOT.TLatex()
    latex_ID.SetNDC()
    latex_ID.SetTextSize(0.03)
    latex_ID.DrawLatex(0.15, 0.85, f"ID: {ID}")
    
    csub.SaveAs(f"{path}/{directory}/p1/subtracted{poly_type}_{sideband_limits}.png")
    csub.SaveAs(f"{path}/{directory}/p1/subtracted{poly_type}_{sideband_limits}.eps")


    return sig_mean, sig_rms,chi2_poly,ndf_poly


lim_num_arr=[5,4,3]
sideband_region_str=["2sig-to-5sig","2sig-to-4sig","2sig-to-3sig"]

poly2_means=[]
poly3_means=[]
poly4_means=[]
means=[]
rms=[]

chi2s=[]

for mm in range(len(lim_num_arr)):
    res2,rms2,chi22,ndf2=signal_analysis("poly2",sideband_region_str[mm],lim_num_arr[mm],thresholdp1)
    poly2_means.append(res2)
    means.append(res2)
    rms.append(rms2)
    chi2s.append(chi22/ndf2)
    all_chi.append(chi22/ndf2)
    res3,rms3,chi23,ndf3=signal_analysis("poly3",sideband_region_str[mm],lim_num_arr[mm],thresholdp1)
    poly3_means.append(res3)
    means.append(res3)
    rms.append(rms3)
    chi2s.append(chi23/ndf3)
    all_chi.append(chi23/ndf3)
    res4,rms4,chi24,ndf4=signal_analysis("poly4",sideband_region_str[mm],lim_num_arr[mm],thresholdp1)
    poly4_means.append(res4)
    means.append(res4)
    rms.append(rms4)
    chi2s.append(chi24/ndf4)
    all_chi.append(chi24/ndf4)

pol2_means=np.array(poly2_means)
pol3_means=np.array(poly3_means)
pol4_means=np.array(poly4_means)
means=np.array(means)
rms=np.array(rms)
chi2s=np.array(chi2s)

n=len(means)

xpoints=np.linspace(1,n,n)

res_chi=ROOT.TGraph(n,xpoints,chi2s)

res_chi.SetMarkerSize(1)
res_chi.SetMarkerStyle(21)

res_graph=ROOT.TGraphErrors(n,xpoints,means,0,rms)

res_graph.SetTitle("p1 values for all fits;Fit No.;p1 (mV/ns)")
res_chi.SetTitle("#Chi^{2}/ndf for all fits;Fit No.;#Chi^{2}/ndf")

res_graph.SetMarkerSize(1)
res_graph.SetMarkerStyle(21)

f = ROOT.TF1("f", "pol0", 1, n)

res_graph.Fit(f, "S R Q")

#for yy in range (n):
 #   res_graph.SetPoint(yy,yy,means[yy])
  #  res_graph.SetPointError(yy,0,rms[yy])

constant = f.GetParameter(0)
error    = f.GetParError(0)
chi2 = f.GetChisquare()
ndf = f.GetNDF()
percent=(error/constant)*100

csig=ROOT.TCanvas("csig","csig",800,600)

res_graph.Draw("AP")

latex.DrawLatex(0.50, 0.80, f"Signal Mean = {constant:.2f}")
latex.DrawLatex(0.50, 0.75, f"Signal Error = {error:.2f}")
latex.DrawLatex(0.50, 0.70, f"Percentage Error = {percent:.2f}")
latex.DrawLatex(0.50, 0.65, f"#chi2/ndf = {chi2:.2f}/{ndf:.2f}")

latex_ID = ROOT.TLatex()
latex_ID.SetNDC()
latex_ID.SetTextSize(0.03)
latex_ID.DrawLatex(0.15, 0.85, f"ID: {ID}")


csig.Modified();
csig.Update();

csig.SaveAs(f"{path}/{directory}/p1/mean_fits.png")
csig.SaveAs(f"{path}/{directory}/p1/mean_fits.eps")

cchi=ROOT.TCanvas("cchi","cchi",800,600)

res_chi.Draw("AP")

latex_ID = ROOT.TLatex()
latex_ID.SetNDC()
latex_ID.SetTextSize(0.03)
latex_ID.DrawLatex(0.15, 0.85, f"ID: {ID}")

cchi.Modified();
cchi.Update();

cchi.SaveAs(f"{path}/{directory}/p1/chi.png")
cchi.SaveAs(f"{path}/{directory}/p1/chi.eps")

error_round=round(error, 1 - int(np.floor(np.log10(abs(error)))) - 1)
decimal_places = -int(np.floor(np.log10(abs(error))))
const_round = round(constant, decimal_places)
now = datetime.now()
now = (now + timedelta(microseconds=500_000)).replace(microsecond=0)

sig_out = pd.DataFrame([[ID],[pres],[FC],[E1],[E2],[E3],[E4],[purity],[constant],[error],[percent]])

inspect = pd.DataFrame([f"{ID} Mean = {const_round} Error = {error_round} ({round(percent,1)}%). Analysis performed at {now}"])

sig_out.T.to_csv(f"{path}/{directory}/signal.csv", mode="w", index=False, header=False)
inspect.T.to_csv(f"{path}/{directory}/signal-inspect.csv", mode="w", index=False, header=False)

sig_out.T.to_csv(f"{path}/results/signals.csv", mode="a", index=False, header=False)
inspect.T.to_csv(f"{path}/results/signals_inspect.csv", mode="a", index=False, header=False)
