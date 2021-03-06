# -*- coding: utf-8 -*-
"""
Created on Fri Mar 20 02:22:58 2020

@author: Jacopo Busatto
"""

import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.metrics import mean_squared_error
from scipy.optimize import curve_fit
from scipy.optimize import fsolve
from scipy.stats import chisquare
import matplotlib.pyplot as plt
import csv 

#Quality for plot saving
DPI=450
#Averaging N for fits errors
SIZE = 100
#days of prediction
NumberOfDaysPredicted=14
#Plot name format:
path='Plots/'
name='-Jacopo'
model='-model-logistic'
# cosa vogliamo analizzare: mi servono per dare nomi alle cose
TypeOfData=['totale_casi','deceduti','dimessi_guariti']
NomeIng=['infected','dead','recovered']
cases=['-infected','-deaths','-recovered']
types=['-linear-','-log-','-ratios-','-derivative-']
region='Italia'
ext='.png'

#devono essere tanti quanti sono le cose da analizzare
YPred_model   =[]
StdPred_model =[]
YPred_model_derivative   =[]
StdPred_model_derivative =[]

# Define analytical model
# Define analytical model
def logistic_model(x,a,b,c):
    return c/(1+np.exp(-(x-b)*a))

def logistic(x,Param):
    return logistic_model(x,Param[0],Param[1],Param[2])

def logistic_model_derivative(x,a,b,c):
    return a*c*np.exp(-a*(x-b))/(1+np.exp(-(x-b)*a))**2

def logistic_derivative(x,Par):
    return Par[0]*Par[2]*np.exp(-Par[0]*(x-Par[1]))/(1+np.exp(-(x-Par[1])*Par[0]))**2


# Prendiamo i dati da Github
url = "https://raw.githubusercontent.com/pcm-dpc/COVID-19/master/dati-andamento-nazionale/dpc-covid19-ita-andamento-nazionale.csv"
dF = pd.read_csv(url, parse_dates=['data'])

LIM=47
iteration=0
for TYPE in TypeOfData:

    df = dF.loc[:,['data',TYPE]]
#    df = dF.loc[:LIM,['data',TYPE]]
    # Formato dati csv
    FMT = '%Y-%m-%dT%H:%M:%S'
    # Formato dati salvataggio
    FMD = '%Y-%m-%d'
    date = df['data']
    DATE = df['data'][len(date)-1].strftime(FMD)
    df['data'] = date.map(lambda x : (x - datetime.strptime("2020-01-01T00:00:00", FMT)).days  )
    namefile=path+DATE+name+model
    x = list(df.iloc[:,0])
    y = list(df.iloc[:,1])
    YERR = np.sqrt(y)
    
    # Fitting logistico
    P0=[0.2,70,60000]
    Par,Cov = curve_fit(logistic_model,x,y,P0, sigma=YERR, absolute_sigma=False)
    ErrPar = [np.sqrt(Cov[ii][ii]) for ii in range(len(Par))]
    
    print('\nlogistic fit parameters for ',NomeIng[iteration],' people')
    print('Rate of growth           =', Par[0])
    print('Peak day from Jan 1st    =', Par[1])
    print('Final number of infected =', Par[2])
    
    #quanti punti considero: fino a che la differenza tra l'asintoto e la funzione non è < 1
    sol = int(fsolve(lambda x : logistic(x,Par) - int(Par[2]),Par[1]))
    pred_x = list(range(max(x),max([int(sol)])))
    xTOT= x+pred_x
    
    # Calcoliamo SIZE funzioni estraendo parametri a caso e facendo la std
    simulated_par= np.random.multivariate_normal(Par, Cov, size=SIZE)
    simulated_curve=[[logistic(ii,par) for ii in xTOT] for par in simulated_par]
    std_fit=np.std(simulated_curve, axis=0)
    Ymin=np.array([logistic(i,Par) for i in xTOT])-np.array(std_fit)
    Ymax=np.array([logistic(i,Par) for i in xTOT])+np.array(std_fit)
    
    y_pred_logistic = [logistic(i,Par) for i in x]
    print('\nMSE logistic curve:    ',mean_squared_error(y,y_pred_logistic))
    
    #chi2 per il fit
    DOF=float(len(x)-len(Par))
    chi2_logistic = chisquare(y, [logistic(ii,Par) for ii in x])[0]/DOF
    print('chi2r = ', chi2_logistic)
    
    
    # Predictions
    Xpredicted =[ii+max(x) for ii in range(1,NumberOfDaysPredicted+1)]
    Ypredicted =[logistic(ii,Par) for ii in Xpredicted]
    Ymin       =np.array([logistic(i,Par) for i in xTOT])-np.array(std_fit)
    Ymax       =np.array([logistic(i,Par) for i in xTOT])+np.array(std_fit)
    YPERR      =np.array([std_fit[i] for i in range(len(x),len(x)+NumberOfDaysPredicted)])
    

    YPred_model   = YPred_model + [np.array(Ypredicted)]
    StdPred_model = StdPred_model + [YPERR]
    
    #PLOTS
    #Plot with predictions
    plt.figure('predictions_'+NomeIng[iteration])
    plt.errorbar(x, y, yerr=YERR, fmt='o',color="red", alpha=0.75,label="Data" )
    plt.errorbar(Xpredicted,Ypredicted, yerr=YPERR, fmt='o',color="orange", alpha=1,label="Predictions ({} days)".format(NumberOfDaysPredicted) )
    plt.fill_between(xTOT,Ymin,Ymax,facecolor='blue', alpha = 0.3 )
    plt.plot(xTOT, [logistic(i,Par) for i in xTOT], 'r',label="Logistic model" )
    plt.legend()
    plt.xlabel("Days since 1 January 2020")
    plt.ylabel('Total number of '+NomeIng[iteration]+'people')
    plt.ylim((min(y)*0.9,Par[2]*1.1))
    plt.grid(linestyle='--',which='both')
    plt.savefig(namefile+cases[iteration]+types[0]+region+ext, dpi=DPI)
    plt.gcf().show()
    #Plot with log predictions
    plt.figure('predictions_'+NomeIng[iteration]+'_log')
    plt.errorbar(x, y, yerr=YERR, fmt='o',color="red", alpha=0.75,label="Data" )
    plt.errorbar(Xpredicted,Ypredicted, yerr=YPERR, fmt='o',color="orange", alpha=1,label="Predictions ({} days)".format(NumberOfDaysPredicted) )
    plt.fill_between(xTOT,Ymin,Ymax,facecolor='blue', alpha = 0.3 )
    plt.semilogy(xTOT, [logistic(i,Par) for i in x+pred_x], 'r',label="logistic model" )
    plt.legend()
    plt.xlabel("Days since 1 January 2020")
    plt.ylabel('Total number of '+NomeIng[iteration]+' people')
    plt.ylim((min(y)*0.9,Par[2]*2))
    plt.grid(linestyle='--',which='both')
    plt.savefig(namefile+cases[iteration]+types[1]+region+ext, dpi=DPI)
    plt.gcf().show()
    
    
    
    
    # Ratio and differences
    Y2=np.array(y)
    Y1=np.array(y)
    Y1=np.delete(Y1,-1)
    Y1=np.insert(Y1,0,Y1[0])
    
    #Plot ratio
    plt.figure('ratios_'+NomeIng[iteration])
    plt.plot(x,Y2/Y1,"--or",markersize=8,label="Ratio",alpha=0.6)
    plt.legend()
    plt.xlabel("Days since 1 January 2020")
    plt.ylabel('Ratio of '+NomeIng[iteration]+' people respect to the day before')
    plt.ylim((min(Y2/Y1)*0.9,max(Y2/Y1)*1.1))
    plt.grid(linestyle='--',which='both')
    plt.savefig(path+DATE+name+cases[iteration]+types[2]+region+ext, dpi=DPI)
    plt.gcf().show()
    
    # differences
    Y2=np.array(y)
    Y1=np.array(y)
    Y1=np.delete(Y1,-1)
    Y1=np.insert(Y1,0,Y1[0])
    Y3=Y2-Y1
    ERRY3=np.sqrt(Y2+Y1)
    
    ParD, CovD = curve_fit(logistic_model_derivative,x,Y3,p0=[0.2,70,64000],sigma=ERRY3, absolute_sigma=False)
    simulated_par_D= np.random.multivariate_normal(ParD, CovD, size=SIZE)
    simulated_curve_D=[[logistic_derivative(ii,par) for ii in list(x)+pred_x] for par in simulated_par_D]
    std_fit_D=np.std(simulated_curve_D, axis=0)
    
    Ymin= np.array([logistic_derivative(i,ParD) for i in list(x)+pred_x])-np.array(std_fit_D)
    Ymax= np.array([logistic_derivative(i,ParD) for i in list(x)+pred_x])+np.array(std_fit_D)
    
    YPred_model_derivative   = YPred_model_derivative + [[logistic_derivative(ii,ParD) for ii in Xpredicted]]
    StdPred_model_derivative = StdPred_model_derivative + [[std_fit_D[ii] for ii in range(len(x),len(x)+NumberOfDaysPredicted)]]    
    # Real data
    plt.figure('derivatives_'+NomeIng[iteration])
    plt.errorbar(x, Y3, yerr=ERRY3, fmt='o',color="red", alpha=0.75,label="Data" )
    plt.plot(list(x)+pred_x, [logistic_derivative(i,ParD) for i in list(x)+pred_x], label="logistic model derivative" )
    plt.fill_between(list(x)+pred_x,Ymin,Ymax,facecolor='blue', alpha = 0.3 )
    plt.legend()
    plt.xlabel("Days since 1 January 2020")
    plt.ylabel('Increase of '+NomeIng[iteration]+' people')
    plt.ylim((min(Y3)*0.9,max([logistic_derivative(i,ParD) for i in list(x)+pred_x])*1.6))
    plt.grid(linestyle='--',which='both')
    plt.savefig(namefile+cases[iteration]+types[3]+region+ext, dpi=DPI)
    plt.gcf().show()
    
    iteration = iteration+1
    #FINE CICLO

totale_attualmente_positivi=np.array(YPred_model[0])-np.array(YPred_model[1])-np.array(YPred_model[2])
std_totale_attualmente_positivi=np.sqrt(np.array(StdPred_model[0])**2+np.array(StdPred_model[1])**2+np.array(StdPred_model[2])**2     )



#IntestazioneCSV
intestCSV=['denominazione_regione','data']
for ii in range(len(TypeOfData)):
    if (ii != 1):
        STD='std_'+TypeOfData[ii]
        intestCSV= intestCSV + [TypeOfData[ii]] + [STD]
    else:
        intestCSV=intestCSV + ['totale_attualmente_positivi','std_totale_attualmente_positivi']
        STD='std_'+TypeOfData[ii]
        intestCSV= intestCSV + [TypeOfData[ii]] + [STD]
for ii in range(len(TypeOfData)):
    STD='std_variazione_'+TypeOfData[ii]
    intestCSV= intestCSV + ['variazione_'+TypeOfData[ii]] + [STD]
    

startingDate=737425
Dates=[datetime.fromordinal(startingDate+ii) for ii in Xpredicted]  
for ii in range(len(Dates)):
    Dates[ii]= Dates[ii].replace(minute=00, hour=18,second=00)
    
writing_list=[]
#RIEMPIAMO L'ARRAY CHE METTEREMO NEL CSV
for ii in range(len(Dates)):
    temp_list=[region,Dates[ii]]
    for jj in range(len(YPred_model)):
        if intestCSV[2+2*jj]=='totale_attualmente_positivi' :
            temp_list=temp_list+[totale_attualmente_positivi[ii]]+[std_totale_attualmente_positivi[ii]]
        temp_list=temp_list+[YPred_model[jj][ii]]+[StdPred_model[jj][ii]]
    # Ora salviamo anche le predizioni sulle derivate
    for jj in range(len(YPred_model_derivative)):
        temp_list=temp_list+[YPred_model_derivative[jj][ii]]+[StdPred_model_derivative[jj][ii]]
    writing_list=writing_list+[temp_list]

with open('model-logistic-national.csv', 'w',newline='') as pred_logistic_file:
    wr = csv.writer(pred_logistic_file, quoting=csv.QUOTE_ALL)
    wr.writerow(intestCSV)
    for ii in range(len(Xpredicted)):
        wr.writerow(writing_list[ii])
