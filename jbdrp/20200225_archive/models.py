import astropy.io.fits as pyfits
import os
from glob import glob
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage.filters import median_filter
from astropy.stats import mad_std
from scipy.signal import correlate2d
from copy import copy
import multiprocessing as mp
from scipy.optimize import minimize
import itertools
import pandas as pd
from wavcal import convolve_spectrum_line_width,convolve_spectrum_pixel_width
from scipy.interpolate import interp1d

def LPFvsHPF(myvec,cutoff):
    myvec_cp = copy(myvec)
    #handling nans:
    wherenans = np.where(np.isnan(myvec_cp))
    window = int(round(np.size(myvec_cp)/(cutoff/2.)/2.))#cutoff
    tmp = np.array(pd.DataFrame(np.concatenate([myvec_cp, myvec_cp[::-1]], axis=0)).interpolate(method="linear").fillna(method="bfill").fillna(method="ffill"))
    myvec_cp_lpf = np.array(pd.DataFrame(tmp).rolling(window=window, center=True).median().interpolate(method="linear").fillna(method="bfill").fillna(method="ffill"))[0:np.size(myvec), 0]
    myvec_cp[wherenans] = myvec_cp_lpf[wherenans]


    fftmyvec = np.fft.fft(np.concatenate([myvec_cp, myvec_cp[::-1]], axis=0))
    LPF_fftmyvec = copy(fftmyvec)
    LPF_fftmyvec[cutoff:(2*np.size(myvec_cp)-cutoff+1)] = 0
    LPF_myvec = np.real(np.fft.ifft(LPF_fftmyvec))[0:np.size(myvec_cp)]
    HPF_myvec = myvec_cp - LPF_myvec


    LPF_myvec[wherenans] = np.nan
    HPF_myvec[wherenans] = np.nan

    # plt.figure(10)
    # plt.plot(myvec_cp,label="fixed")
    # plt.plot(myvec,label="ori")
    # plt.plot(myvec_cp_lpf,label="lpf")
    # plt.plot(LPF_myvec,label="lpf fft")
    # plt.show()
    return LPF_myvec,HPF_myvec



if __name__ == "__main__":
    try:
        import mkl

        mkl.set_num_threads(1)
    except:
        pass
    #temporary test, wavcal comparison
    if 0:
        ef = 2
        mykpicdir = "/scr3/jruffio/data/kpic/"
        kap_And_dir = os.path.join(mykpicdir, "kap_And_20191107")
        out = os.path.join(kap_And_dir, "calib", "wvs_f{0}.fits".format(ef))
        hdulist = pyfits.open(out)
        kap_And_wvs = hdulist[0].data
        bet_Peg_dir = os.path.join(mykpicdir, "bet_Peg_20191108")
        out = os.path.join(bet_Peg_dir, "calib", "wvs_f{0}.fits".format(1))
        hdulist = pyfits.open(out)
        bet_Peg_wvs1 = hdulist[0].data
        out = os.path.join(bet_Peg_dir, "calib", "wvs_f{0}.fits".format(2))
        hdulist = pyfits.open(out)
        bet_Peg_wvs2 = hdulist[0].data
        out = os.path.join(bet_Peg_dir, "calib", "wvs_f{0}.fits".format(3))
        hdulist = pyfits.open(out)
        bet_Peg_wvs3 = hdulist[0].data
        out = os.path.join(bet_Peg_dir, "calib", "nspec191108_0020_star_wvs_f2_ef2.fits")
        hdulist = pyfits.open(out)
        jason_wvs = hdulist[0].data
        out = os.path.join(bet_Peg_dir, "calib", "wvs_combined_images_f{0}.fits".format(ef))
        hdulist = pyfits.open(out)
        bet_Peg_wvs_combined = hdulist[0].data

        # for k in range(9)
        #     plt.subplot(1,9,8-k)
        k = 6
        dwv = jason_wvs[k,1:2048]-jason_wvs[k,0:2047]
        dwv = np.append(dwv,dwv[-1])
        # plt.title("Order of the CO bandhead (#7)")
        plt.title("Order {0}".format(k+1))
        plt.plot((kap_And_wvs[k,:]-jason_wvs[k,:])/dwv,label="f2: telluric only (Kap And)")
        plt.plot((bet_Peg_wvs1[k,:]-jason_wvs[k,:])/dwv,label="f1: M star (bet Peg)")
        plt.plot((bet_Peg_wvs2[k,:]-jason_wvs[k,:])/dwv,label="f2: M star (bet Peg)")
        plt.plot((bet_Peg_wvs3[k,:]-jason_wvs[k,:])/dwv,label="f3: M star (bet Peg)")
        plt.plot((bet_Peg_wvs_combined[k,:]-jason_wvs[k,:])/dwv,label="f2: M star (combined, bet Peg)")
        plt.plot(np.zeros(jason_wvs[k,:].shape),label="f2: Jason (bet Peg)") #jason_wvs[k,:]
        plt.ylabel("offset wrt Jason (pix)")
        plt.xlabel("wv (mum)")
        plt.legend()
        plt.show()



    mykpicdir = "/scr3/jruffio/data/kpic/"
    # kap_And_dir = os.path.join(mykpicdir, "kap_And_20191107")
    kap_And_dir = os.path.join(mykpicdir,"DH_Tau_20191108")
    # kap_And_dir = os.path.join(mykpicdir,"kap_And_20191013")
    # kap_And_dir = os.path.join(mykpicdir,"2M0746A_20191012")
    # kap_And_dir = os.path.join(mykpicdir,"2M0746B_20191012")



    ef = 3
    # selec_orders = [6]
    # selec_orders = [6]
    selec_orders = [6]
    # selec_orders = [1,2,6,7,8]
    cutoff = 20
    if 1:
        star_spec_f2_filename = glob(os.path.join(kap_And_dir, "calib","nspec*_star_spectra_f{0}_ef{0}.fits".format(ef)))[0]
        # star_spec_f2_filename = glob(os.path.join(kap_And_dir, "calib","nspec*_refstar_spectra_f{0}_ef{0}.fits".format(ef)))[0]
        print(star_spec_f2_filename)
        hdulist = pyfits.open(star_spec_f2_filename)
        # star_spectra = hdulist[0].data[:,:,::-1]
        star_spectra = hdulist[0].data
        star_spectra = star_spectra[:,selec_orders,50:2000]
        hdulist = pyfits.open(star_spec_f2_filename.replace("_spectra_","_spectraerr_"))
        # star_err =  hdulist[0].data[:,:,::-1]
        star_err =  hdulist[0].data
        star_err = star_err[:,selec_orders,50:2000]
        if 1:
            hdulist = pyfits.open(star_spec_f2_filename.replace("_spectra_","_wvs_"))
            star_wvs = hdulist[0].data[selec_orders,50:2000]
        else:
            # out = os.path.join(kap_And_dir, "calib", "wvs_f{0}.fits".format(ef))
            out = os.path.join(os.path.join(mykpicdir, "bet_Peg_20191108"), "calib", "wvs_f{0}.fits".format(ef))
            hdulist = pyfits.open(out)
            star_wvs = hdulist[0].data[selec_orders,50:2000]
        # print(star_wvs.shape)
        # exit()
    else:
        star_spec_f2_filename = glob(os.path.join(kap_And_dir, "calib","nspec*_science_spectra_f2_ef3.fits"))[0]
        print(star_spec_f2_filename)
        hdulist = pyfits.open(star_spec_f2_filename)
        # star_spectra = hdulist[0].data[:,:,::-1]
        star_spectra = hdulist[0].data
        star_spectra = star_spectra[:,selec_orders,50:2000]
        hdulist = pyfits.open(star_spec_f2_filename.replace("_spectra_","_spectraerr_"))
        # star_err =  hdulist[0].data[:,:,::-1]
        star_err =  hdulist[0].data
        star_err = star_err[:,selec_orders,50:2000]
        if 1:
            hdulist = pyfits.open(star_spec_f2_filename.replace("_spectra_","_wvs_"))
            star_wvs = hdulist[0].data[selec_orders,50:2000]
        else:
            # out = os.path.join(kap_And_dir, "calib", "wvs_f{0}.fits".format(3))
            out = os.path.join(os.path.join(mykpicdir, "bet_Peg_20191108"), "calib", "wvs_f{0}.fits".format(ef))
            hdulist = pyfits.open(out)
            star_wvs = hdulist[0].data[selec_orders,50:2000]

        # y = np.ravel(star_spectra)
        # x = np.ravel(np.tile(star_wvs)
        # a = np.where(np.isfinite(y))
        # y = y[a]
        # x = x[a]
        # star_spline = interpolate.splrep(x, y)





    science_spec_f2_filename = glob(os.path.join(kap_And_dir, "calib","nspec*_science_spectra_f2_ef{0}.fits".format(ef)))[0]
    print(science_spec_f2_filename)
    hdulist = pyfits.open(science_spec_f2_filename)
    # science_spectra = hdulist[0].data[:,:,::-1]
    science_spectra = hdulist[0].data
    science_spectra = science_spectra[:,selec_orders,50:2000]
    # science_spectra = science_spectra[[0,],:,:]
    hdulist = pyfits.open(science_spec_f2_filename.replace("_spectra_","_spectraerr_"))
    # science_err = hdulist[0].data[:,:,::-1]
    science_err = hdulist[0].data
    science_err = science_err[:,selec_orders,50:2000]
    # science_err = science_err[[0,],:,:]
    hdulist = pyfits.open(science_spec_f2_filename.replace("_spectra_","_wvs_"))
    science_wvs = hdulist[0].data[selec_orders,50:2000]
    # out = os.path.join(kap_And_dir, "calib", "wvs_f{0}.fits".format(ef))
    # out = os.path.join(os.path.join(mykpicdir, "bet_Peg_20191108"), "calib", "wvs_f{0}.fits".format(ef))
    # hdulist = pyfits.open(out)
    # science_wvs = hdulist[0].data[selec_orders,50:2000]
    # science_wvs = star_wvs
    print(star_spectra.shape)
    print(science_spectra.shape)
    print(science_wvs.shape)
    # exit()
    N_order = science_wvs.shape[0]

    # star_spectra = interpolate.splev(science_wvs, star_spline, der=0)
    # star_wvs = science_wvs


    hdulist = pyfits.open(os.path.join(kap_And_dir, "calib", "trace_calib_polyfit_fiber{0}.fits".format(ef)))
    science_lw = np.abs(hdulist[0].data[:, :, 1])
    science_lw = science_lw[selec_orders,50:2000]
    print(science_lw.shape)
    tmp_dwvs = science_wvs[:, 1:science_wvs.shape[-1]] - science_wvs[:, 0:science_wvs.shape[-1]-1]
    tmp_dwvs = np.concatenate([tmp_dwvs, tmp_dwvs[:, -1][:, None]], axis=1)
    science_lw_wvunit = science_lw * tmp_dwvs
    line_width_func = interp1d(np.ravel(science_wvs), np.ravel(science_lw_wvunit), bounds_error=False,
                               fill_value=np.nan)
    pixel_width_func = interp1d(np.ravel(science_wvs), np.ravel(tmp_dwvs), bounds_error=False, fill_value=np.nan)

    if 1:
        # combined_science_spectra = np.nansum(science_spectra/science_err**2,axis=0)/np.nansum(1/science_err**2,axis=0)
        combined_science_spectra = np.nansum(science_spectra,axis=0)
        where_nans = np.where(np.sum(np.isfinite(science_spectra), axis=0) == 0)
        combined_science_spectra[where_nans] = np.nan
        combined_science_err = 1/np.sqrt(np.nansum(1/science_err**2,axis=0))
        combined_science_err[where_nans] = np.nan
        combined = True
    # for im_id,(combined_science_spectra,combined_science_err) in enumerate(zip(science_spectra,science_err)):
    #     combined = False

        # plt.plot(np.ravel(combined_science_spectra),label="{0}".format(im_id))
    # plt.legend()
    #
    # plt.figure(2)
    # plt.plot(np.nanmean(science_spectra,axis=(1,2)))
    # plt.show()
    # exit()
    # if 1:

        med_star_spec = np.nanmedian(star_spectra, axis=0)
        for k in range(star_spectra.shape[0]):
            for l in range(N_order):
                wherefinite = np.where(np.isfinite(star_spectra[k, l, :]) * np.isfinite(med_star_spec[l, :]))[0]
                scaling = np.nansum(star_spectra[k, l, wherefinite] * med_star_spec[l, wherefinite]) / np.nansum(star_spectra[k, l, wherefinite] ** 2)
                star_spectra[k, l, :] = star_spectra[k, l, :] * scaling
                star_err[k, l, :] = star_err[k, l, :] * scaling
        # combined_star_spectra = np.nansum(star_spectra/star_err**2,axis=0)/np.nansum(1/star_err**2,axis=0)
        combined_star_spectra = np.nansum(star_spectra,axis=0)
        where_nans = np.where(np.sum(np.isfinite(star_spectra), axis=0) == 0)
        combined_star_spectra[where_nans] = np.nan
        combined_star_err = 1/np.sqrt(np.nansum(1/star_err**2,axis=0))
        combined_star_err[where_nans] = np.nan

        combined_science_spectra[where_nans] = np.nan

        specpool = mp.Pool(processes=30)
        if 0:
            travis_spec_filename = os.path.join("/scr3/jruffio/data/kpic/models/planets_templates/",
                                                "KapAnd_lte19-3.50-0.0.AGSS09.Dusty.Kzz=0.0.PHOENIX-ACES-2019.7.save")
            import scipy.io as scio
            travis_spectrum = scio.readsav(travis_spec_filename)
            ori_planet_spec = np.array(travis_spectrum["f"])
            wmod = np.array(travis_spectrum["w"]) / 1.e4
            crop_plmodel = np.where((wmod>1.8-(2.6-1.8)/2)*(wmod<2.6+(2.6-1.8)/2))
            wmod = wmod[crop_plmodel]
            ori_planet_spec = ori_planet_spec[crop_plmodel]
            # planet_convspec = convolve_spectrum(wmod, ori_planet_spec, 30000, specpool)
            if 1:
                pl_line_widths = np.array(pd.DataFrame(line_width_func(wmod)).interpolate(method="linear").fillna(method="bfill").fillna(method="ffill"))[:, 0]
                pl_pixel_widths = np.array(pd.DataFrame(pixel_width_func(wmod)).interpolate(method="linear").fillna(method="bfill").fillna(method="ffill"))[:, 0]
                planet_convspec = convolve_spectrum_line_width(wmod,ori_planet_spec,pl_line_widths,mypool=specpool)
                planet_convspec = convolve_spectrum_pixel_width(wmod,planet_convspec,pl_pixel_widths,mypool=specpool)
            planet_convspec /= np.nanmean(planet_convspec)
            print("convolving: " + travis_spec_filename)
            #
            # kap_And_spec_func = interp1d(wmod, planet_convspec, bounds_error=False, fill_value=np.nan)
            from scipy import interpolate
            kap_And_spec_spline0 = interpolate.splrep(wmod, planet_convspec)

        else:
            with open("/scr3/jruffio/data/kpic/models/planets_templates/lte018-5.0-0.0a+0.0.BT-Settl.spec.7", 'r') as f:
                model_wvs = []
                model_fluxes = []
                for line in f.readlines():
                    line_args = line.strip().split()
                    model_wvs.append(float(line_args[0]))
                    model_fluxes.append(float(line_args[1].replace('D', 'E')))
            model_wvs = np.array(model_wvs)/1.e4
            model_fluxes = np.array(model_fluxes)
            model_fluxes = 10 ** (model_fluxes - 8)
            crop_plmodel = np.where((model_wvs>1.8-(2.6-1.8)/2)*(model_wvs<2.6+(2.6-1.8)/2))
            model_wvs = model_wvs[crop_plmodel]
            model_fluxes = model_fluxes[crop_plmodel]
            # planet_convspec = convolve_spectrum(wmod, ori_planet_spec, 30000, specpool)
            if 1:
                pl_line_widths = np.array(pd.DataFrame(line_width_func(model_wvs)).interpolate(method="linear").fillna(method="bfill").fillna(method="ffill"))[:, 0]
                pl_pixel_widths = np.array(pd.DataFrame(pixel_width_func(model_wvs)).interpolate(method="linear").fillna(method="bfill").fillna(method="ffill"))[:, 0]
                planet_convspec = convolve_spectrum_line_width(model_wvs,model_fluxes,pl_line_widths,mypool=specpool)
                planet_convspec = convolve_spectrum_pixel_width(model_wvs,planet_convspec,pl_pixel_widths,mypool=specpool)
            planet_convspec /= np.nanmean(planet_convspec)
            #
            # kap_And_spec_func = interp1d(wmod, planet_convspec, bounds_error=False, fill_value=np.nan)
            from scipy import interpolate
            kap_And_spec_spline = interpolate.splrep(model_wvs, planet_convspec)

            # plt.plot(model_wvs,model_fluxes/np.mean(model_fluxes),label="Settl")
            # plt.plot(model_wvs,planet_convspec/np.mean(planet_convspec),label="Settl conv")
            # plt.plot(wmod,ori_planet_spec/np.mean(ori_planet_spec),label="Phoenix")
            # plt.legend()
            # plt.show()

        # plt.figure(10)
        # wmod_new = np.linspace(wmod[0],wmod[-1],1e5)
        # plt.plot(wmod, ori_planet_spec/np.nanmean(ori_planet_spec),label="ori")
        # # plt.plot(wmod_new, kap_And_spec_func(wmod_new),label="conv linear")
        # plt.plot(wmod_new, interpolate.splev(wmod_new,kap_And_spec_spline,der=0),label="conv spline")
        # plt.legend()
        # plt.show()
        # # specpool.join()
        # # specpool.close()

        phoenix_folder = "/scr3/jruffio/data/kpic/models/phoenix/"
        phoenix_wv_filename = os.path.join(phoenix_folder,"WAVE_PHOENIX-ACES-AGSS-COND-2011.fits")
        with pyfits.open(phoenix_wv_filename) as hdulist:
            phoenix_wvs = hdulist[0].data/1.e4
        crop_phoenix = np.where((phoenix_wvs>1.8-(2.6-1.8)/2)*(phoenix_wvs<2.6+(2.6-1.8)/2))
        phoenix_wvs = phoenix_wvs[crop_phoenix]
        phoenix_model_host_filename = glob(os.path.join(phoenix_folder, "kap_And" + "*.fits"))[0]
        with pyfits.open(phoenix_model_host_filename) as hdulist:
            phoenix_HR8799 = hdulist[0].data[crop_phoenix]
        print("convolving: "+phoenix_model_host_filename)
        # phoenix_HR8799_conv = convolve_spectrum(phoenix_wvs,phoenix_HR8799,30000,specpool)
        # planet_convspec = convolve_spectrum(wmod, ori_planet_spec, 30000, specpool)
        if 1:
            phoenix_line_widths = np.array(pd.DataFrame(line_width_func(phoenix_wvs)).interpolate(method="linear").fillna(method="bfill").fillna(method="ffill"))[:, 0]
            phoenix_pixel_widths = np.array(pd.DataFrame(pixel_width_func(phoenix_wvs)).interpolate(method="linear").fillna(method="bfill").fillna(method="ffill"))[:, 0]
            phoenix_HR8799_conv = convolve_spectrum_line_width(phoenix_wvs,phoenix_HR8799,phoenix_line_widths,mypool=specpool)
            phoenix_HR8799_conv = convolve_spectrum_pixel_width(phoenix_wvs,phoenix_HR8799_conv,phoenix_pixel_widths,mypool=specpool)
        phoenix_HR8799_conv /= np.nanmean(phoenix_HR8799_conv)
        # phoenix_HR8799_spline = interpolate.splrep(phoenix_wvs, phoenix_HR8799_conv)
        from scipy.interpolate import interp1d
        phoenix_HR8799_func = interp1d(phoenix_wvs, phoenix_HR8799_conv, bounds_error=False, fill_value=np.nan)

        phoenix_model_host_filename = glob(os.path.join(phoenix_folder, "bet_Peg" + "*.fits"))[0]
        with pyfits.open(phoenix_model_host_filename) as hdulist:
            phoenix_HR8799 = hdulist[0].data[crop_phoenix]
        print("convolving: "+phoenix_model_host_filename)
        # phoenix_HR8799_conv = convolve_spectrum(phoenix_wvs,phoenix_HR8799,30000,specpool)
        # planet_convspec = convolve_spectrum(wmod, ori_planet_spec, 30000, specpool)
        if 1:
            phoenix_line_widths = np.array(pd.DataFrame(line_width_func(phoenix_wvs)).interpolate(method="linear").fillna(method="bfill").fillna(method="ffill"))[:, 0]
            phoenix_pixel_widths = np.array(pd.DataFrame(pixel_width_func(phoenix_wvs)).interpolate(method="linear").fillna(method="bfill").fillna(method="ffill"))[:, 0]
            phoenix_HR8799_conv = convolve_spectrum_line_width(phoenix_wvs,phoenix_HR8799,phoenix_line_widths,mypool=specpool)
            phoenix_HR8799_conv = convolve_spectrum_pixel_width(phoenix_wvs,phoenix_HR8799_conv,phoenix_pixel_widths,mypool=specpool)
        phoenix_HR8799_conv /= np.nanmean(phoenix_HR8799_conv)
        # phoenix_HR8799_spline = interpolate.splrep(phoenix_wvs, phoenix_HR8799_conv)
        from scipy.interpolate import interp1d
        phoenix_betPeg_func = interp1d(phoenix_wvs, phoenix_HR8799_conv, bounds_error=False, fill_value=np.nan)
        # plt.figure(10)
        # phoenix_wvs_new = np.linspace(phoenix_wvs[0],phoenix_wvs[-1],1e6)
        # plt.plot(phoenix_wvs, phoenix_HR8799,label="ori")
        # plt.plot(phoenix_wvs_new, phoenix_HR8799_func(phoenix_wvs_new),label="conv lin")
        # # plt.plot(phoenix_wvs_new,  interpolate.splev(phoenix_wvs_new,phoenix_HR8799_spline,der=0),label="conv")
        # plt.legend()
        # plt.show()
        # exit()

        where_data_nans = np.where(np.isnan(combined_science_spectra))
        transmission = combined_star_spectra/phoenix_HR8799_func(science_wvs)
        transmission[where_data_nans] = np.nan

        if 0: #injecting fake planet
            c_kms = 299792.458
            rv0 = 10
            print(combined_science_spectra.shape)
            print(np.nanmedian(combined_science_spectra))
            ampl = 0.5*np.nanmedian(combined_science_spectra)
            combined_science_spectra_ori = copy(combined_science_spectra)
            fake = interpolate.splev(science_wvs * (1 - rv0 / c_kms), kap_And_spec_spline, der=0) * transmission
            fake[where_data_nans] = np.nan
            fake = ampl * fake/np.nanmedian(fake)
            combined_science_spectra += fake
            # plt.plot(np.ravel(science_wvs),np.ravel(combined_science_spectra_ori), label="original data")
            # plt.plot(np.ravel(science_wvs),np.ravel(fake), label="Fake")
            # plt.plot(np.ravel(science_wvs),np.ravel(combined_science_spectra), label="Data + fake")
            # plt.legend()
            # plt.show()
            # exit()


        if 1:
            combined_science_spectra_hpf = np.zeros(combined_science_spectra.shape)
            combined_science_spectra_lpf = np.zeros(combined_science_spectra.shape)
            for order_id in range(N_order):
                p = combined_science_spectra[order_id,:]
                p_lpf, p_hpf = LPFvsHPF(p, cutoff=cutoff)
                combined_science_spectra_lpf[order_id,:] = p_lpf
                combined_science_spectra_hpf[order_id,:] = p_hpf

                # plt.plot(p)
                # plt.plot(p_hpf)
                # plt.plot(p_lpf)
                # plt.show()


            m2 = phoenix_HR8799_func(science_wvs)*transmission
            # m2 = phoenix_betPeg_func(science_wvs)*transmission
            for order_id in range(N_order):
                m2_tmp_lpf,m2_tmp_hpf= LPFvsHPF(m2[order_id, :], cutoff=cutoff)
                # plt.plot(m2[order_id, :])
                # plt.plot(m2_tmp_lpf)
                # plt.plot(m2_tmp_hpf)
                # plt.show()
                m2[order_id,:] =  m2_tmp_hpf/m2_tmp_lpf* combined_science_spectra_lpf[order_id,:]

            rv_list = np.concatenate([np.arange(-300,-20,3),np.arange(-20,20,0.5),np.arange(20,300,3)], axis=0)
            # rv_list = np.arange(0,60,1)[:,None]
            if combined:
                out = np.zeros(rv_list.shape)
            else:
                out = np.zeros((science_spectra.shape[0],np.size(rv_list)))
            for rv_id, rv in enumerate(rv_list):
                print(rv_id,np.size(rv_list))
                c_kms = 299792.458
                m1 = interpolate.splev(science_wvs*(1-rv/c_kms),kap_And_spec_spline,der=0)*transmission
                for order_id in range(N_order):
                    m1[order_id,:] =  LPFvsHPF(m1[order_id,:], cutoff=cutoff)[1]
                # combined_science_spectra_hpf[np.where(np.isnan(m1)*np.isnan(m2))] = np.nan

                ravelHPFdata = np.ravel(combined_science_spectra_hpf)
                ravelwvs = np.ravel(science_wvs)

                where_data_finite = np.where(np.isfinite(ravelHPFdata))
                ravelHPFdata = ravelHPFdata[where_data_finite]
                ravelwvs = ravelwvs[where_data_finite]
                sigmas_vec = np.ravel(combined_science_err)[where_data_finite]
                logdet_Sigma = np.sum(2*np.log(sigmas_vec))

                m1_ravel = np.ravel(m1)[where_data_finite]
                m2_ravel = np.ravel(m2)[where_data_finite]
                HPFmodel_H0 = m2_ravel[:,None]
                HPFmodel = np.concatenate([m1_ravel[:,None], m2_ravel[:,None]], axis=1)
                # HPFmodel = m1_ravel[:,None]

                # print(np.where(np.isnan( ravelHPFdata/sigmas_vec)))
                # print(np.where(np.isnan( HPFmodel/sigmas_vec[:,None])))
                HPFparas, HPFchi2, rank, s = np.linalg.lstsq(HPFmodel/sigmas_vec[:,None], ravelHPFdata/sigmas_vec, rcond=None)
                HPFparas_H0, HPFchi2_H0, rank, s = np.linalg.lstsq(HPFmodel_H0/sigmas_vec[:,None], ravelHPFdata/sigmas_vec, rcond=None)
                # print("H1",HPFparas)
                # print("H0",HPFparas_H0)
                # # plt.fill_between(ravelwvs,ravelHPFdata-sigmas_vec,ravelHPFdata+sigmas_vec, label = "error")
                # plt.plot(ravelwvs,ravelHPFdata,label = "data",alpha= 0.5)
                # # plt.plot(ravelwvs,HPFparas[0]*m1_ravel, label = "planet",alpha= 0.5)
                # plt.plot(ravelwvs,HPFparas[1]*m2_ravel, label = "star",alpha= 0.5)
                # # plt.plot(ravelwvs,ravelHPFdata-HPFparas[1]*m2_ravel, label = "res",alpha= 0.5)
                # plt.legend()
                # plt.show()
                # exit()

                data_model = np.dot(HPFmodel, HPFparas)
                data_model_H0 = np.dot(HPFmodel_H0, HPFparas_H0)
                deltachi2 = 0  # chi2ref-np.sum(ravelHPFdata**2)
                ravelresiduals = ravelHPFdata - data_model
                ravelresiduals_H0 = ravelHPFdata - data_model_H0
                HPFchi2 = np.nansum((ravelresiduals) ** 2)
                HPFchi2_H0 = np.nansum((ravelresiduals_H0) ** 2)

                Npixs_HPFdata = HPFmodel.shape[0]
                minus2logL_HPF = Npixs_HPFdata * (1 + np.log(HPFchi2 / Npixs_HPFdata) + logdet_Sigma + np.log(2 * np.pi))
                minus2logL_HPF_H0 = Npixs_HPFdata * (1 + np.log(HPFchi2_H0 / Npixs_HPFdata) + logdet_Sigma + np.log(2 * np.pi))
                AIC_HPF = 2 * (HPFmodel.shape[-1]) + minus2logL_HPF
                AIC_HPF_H0 = 2 * (HPFmodel_H0.shape[-1]) + minus2logL_HPF_H0

                if combined:
                    out[rv_id] = AIC_HPF_H0-AIC_HPF
                    # out[rv_id] = HPFparas[0]
                else:
                    out[im_id,rv_id] = AIC_HPF_H0-AIC_HPF
                    # out[im_id,rv_id] = HPFparas[0]
        if combined:
            out = out - np.nanmedian(out)
            plt.plot(rv_list,out/np.nanstd(out),alpha=0.5)
        else:
            out[im_id, :] = out[im_id, :] - np.nanmedian(out[im_id, :])
            plt.plot(rv_list,out[im_id, :],alpha=0.5,label="{0}".format(im_id))
    if not combined:
        ccf =np.nanmean(out, axis=0)
        plt.plot(rv_list,ccf)
        plt.legend()
    plt.show()
