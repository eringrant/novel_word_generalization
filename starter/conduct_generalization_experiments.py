#!/usr/bin/python


from __future__ import print_function, division


from argparse import ArgumentParser
from ConfigParser import ConfigParser
import itertools
import logging
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from multiprocessing import Pool
import numpy as np
import os
import re
import sys
import types


import generalization_experiment


"""
conduct_generalization_experiments.py

Run the generalization experiments with the parameter setting(s) defined in the
config file (identified by the optional command line argument CONFIG); use
the number of CPU cores specified by the optional command line argument CORES:

python novel_word_generalization_experiments.py -c CONFIG -n CORES

The default values are CONFIG=exp.cfg and CORES=1.
"""


def generate_conditions(paramlist):

    if isinstance(type(paramlist), types.DictType):
        paramlist = [paramlist]

    iparamlist = []
    for params in paramlist:
        if ('experiment' in params and params['experiment'] == 'single'):
            iparamlist.append(params)  # only do one repetition of experiment
        else:
            iterparams = [p for p in params if hasattr(params[p], '__iter__')]
            if len(iterparams) > 0:
                iterfunc = itertools.product
                for il in iterfunc(*[params[p] for p in iterparams]):
                    par = params.copy()  # keep the params having only one value
                    for i, ip in enumerate(iterparams):
                        par[ip] = il[i]
                    iparamlist.append(par)
            else:
                iparamlist.append(params)

    return iparamlist


def items_to_params(items):
    params = {}
    for t, v in items:
        try:  # evaluating the parameter
            params[t] = eval(v)
            if isinstance(params[t], np.ndarray):
                params[t] = params[t].tolist()
        except (NameError, SyntaxError):
            params[t] = v
    return params


def plot_results_as_bar_chart(results, savename=None,
                              normalise_over_test_scene=True, annotation=None,
                              y_limit=None):

    #conditions = [
    #    'one example',
    #    'three subordinate examples',
    #    'three basic-level examples',
    #    'three superordinate examples'
    #]
    conditions = [
        u'one example',
        u'two subordinate examples',
        u'two basic-level examples',
        u'two superordinate examples',
        u'three subordinate examples',
        u'three basic-level examples',
        u'three superordinate examples',
        u'four subordinate examples',
        u'four basic-level examples',
        u'four superordinate examples',
    ]

    ind = np.array([2*n for n in range(len(results))])
    width = 0.25

    l0 = [np.mean(results[cond]['subordinate matches']) for cond in conditions]
    l1 = [np.mean(results[cond]['basic-level matches']) for cond in conditions]
    l2 = [np.mean(results[cond]['superordinate matches']) for cond in conditions]

    error0 = [np.std(results[cond]['subordinate matches']) for cond in conditions]
    error1 = [np.std(results[cond]['basic-level matches']) for cond in conditions]
    error2 = [np.std(results[cond]['superordinate matches']) for cond in conditions]

    if normalise_over_test_scene is True:

        denom = [np.mean(results[cond]['subordinate matches']) for cond in conditions]

        # If the following two lines are uncommented, then the results are normalized over the test scene
        # If not, the results are scaled to the probability of the subordinate match
        #denom = np.add(denom, [np.mean(results[cond]['basic-level matches']) for cond in conditions])
        #denom = np.add(denom, [np.mean(results[cond]['superordinate matches']) for cond in conditions])

        l0 = np.array(l0)
        l1 = np.array(l1)
        l2 = np.array(l2)

        try:
            l0 /= denom
        except ZeroDivisionError:
            pass
        try:
            l1 /= denom
        except ZeroDivisionError:
            pass
        try:
            l2 /= denom
        except ZeroDivisionError:
            pass

        l0 = list(l0)
        l1 = list(l1)
        l2 = list(l2)

        error0 = np.array(error0)
        error1 = np.array(error1)
        error2 = np.array(error2)

        try:
            error0 /= denom
        except ZeroDivisionError:
            pass
        try:
            error1 /= denom
        except ZeroDivisionError:
            pass
        try:
            error2 /= denom
        except ZeroDivisionError:
            pass

        error0 = list(error0)
        error1 = list(error1)
        error2 = list(error2)

    width = 0.5
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.bar(ind + width, l0, width, color='r', yerr=error0)
    ax.bar(ind + 2*width, l1, width, color='g', yerr=error1)
    ax.bar(ind + 3*width, l2, width, color='b', yerr=error2)

    ax.set_ylabel("generalization probability")
    ax.set_xlabel("training condition")

    #short_form_conditions = [
    #    '1 ex.',
    #    '3 subord.',
    #    '3 basic',
    #    '3 super.'
    #]
    short_form_conditions = conditions[:]
    short_form_conditions = [s.replace('example', 'ex') for s in short_form_conditions]
    short_form_conditions = [s.replace('subordinate', 'subord') for s in short_form_conditions]
    short_form_conditions = [s.replace('basic-level', 'basic') for s in short_form_conditions]
    short_form_conditions = [s.replace('superordinate', 'super') for s in short_form_conditions]
    ax.set_xticklabels([short_form_conditions[i//2] if (i+1) % 2 == 0 else '' \
                        for i in range(2*len(short_form_conditions))])

    m = np.max(l0 + l1 + l2)

    if y_limit:
        plt.ylim((0, y_limit))
    elif normalise_over_test_scene is True:
        plt.ylim((0, 1))
    else:
        plt.ylim((0, float(m)))

    #lgd = plt.legend((p0, p1, p2), ('subord.', 'basic', 'super.'),
                     #loc='upper right')

    title = "Generalization scores"

    if annotation is not None:
        title += '\n' + annotation

    if savename is None:
        plt.show()
    else:
        #plt.savefig(savename, bbox_extra_artists=(lgd,), bbox_inches='tight')
        plt.savefig(savename, bbox_inches='tight')

    plt.close()


def replace_with_underscores(s):
    s = re.sub(r"[^\w\s-]", '', s)
    s = re.sub(r"\s+", '_', s)
    return s


def run_trial(params):
    """
    Conduct a trial of the novel word generalization experiment, under the
    parameter settings specified in params.
    """
    if (not params['learner-type'] == 'child') or (params['learner-type'] ==
                                                   'child' and
                                                   check_for_child_params(params)):
        experiment = generalization_experiment.Experiment(params)
        results = experiment.run()

        # Create a title for the plots PNG image
        title = ''
        #title += ',' + 'featurespace_' + params['feature-space']
        #title += ',' + 'alpha_' + str(params['alpha'])
        #title += ',' + 'beta_' + str(params['beta'])
        #title += ',' + 'gammasup_' + str(params['gamma-sup'])
        #title += ',' + 'gammabas_' + str(params['gamma-basic'])
        #title += ',' + 'gammasub_' + str(params['gamma-sub'])
        #title += ',' + 'gammainst_' + str(params['gamma-instance'])
        #title += ',' + 'k_' + str(params['k-sup'])
        #title += ',' + 'kbas_' + str(params['k-basic'])
        #title += ',' + 'ksub_' + str(params['k-sub'])
        #title += ',' + 'kinst_' + str(params['k-instance'])
        #title += ',' + 'psup_' + str(params['p-sup'])
        #title += ',' + 'pbasic_' + str(params['p-basic'])
        #title += ',' + 'psub_' + str(params['p-sub'])
        #title += ',' + 'pinstance_' + str(params['p-instance'])
        title += ',' + 'decaysup_' + str(params['decay-sup'])
        title += ',' + 'decaybas_' + str(params['decay-basic'])
        title += ',' + 'decaysub_' + str(params['decay-sub'])
        title += ',' + 'decayinst_' + str(params['decay-instance'])
        #title += ',' + 'fwsup_' + str(params['feature-weight-sup'])
        #title += ',' + 'fwbasic_' + str(params['feature-weight-basic'])
        #title += ',' + 'fwsub_' + str(params['feature-weight-sub'])
        #title += ',' + 'fwinstance_' + str(params['feature-weight-instance'])
        #title += ',' + 'subtractprior_' + str(params['subtract-prior'])
        #title += ',' + 'metric_' + str(params['metric'])
        title += ',' + 'spacing_' + params['spacing-condition']
        title += ',' + 'test_' + "%03d" % params['test-delay']

        title = title.lstrip(',')

        if not os.path.exists(params['output-path']):
            os.makedirs(params['output-path'])
        if not os.path.exists(os.path.join(params['output-path'], 'plots')):
            os.makedirs(os.path.join(params['output-path'], 'plots'))
        if not os.path.exists(os.path.join(params['output-path'], 'csv')):
            os.makedirs(os.path.join(params['output-path'], 'csv'))
        if not os.path.exists(os.path.join(params['output-path'], 'sc')):
            os.makedirs(os.path.join(params['output-path'], 'sc'))

        if (not params['check-xt-condition'] and not\
            params['check-spencer-condition'])\
            or (params['check-xt-condition'] and xt_condition(results, params))\
            or (params['check-spencer-condition'] and\
                spencer_condition(results, params)):
            plot_results_as_bar_chart(results,
                                    savename=os.path.join(params['output-path'],
                                                            'plots', title)+ '.png',
                                    normalise_over_test_scene=True if
                                      params['metric'] == 'intersection' else
                                      True)
            write_suspicious_coincidence(results,
                                    savename=os.path.join(params['output-path'],
                                                            'sc', title)+ '.dat')
            write_results_as_csv_file(results,
                                    savename=os.path.join(params['output-path'],
                                                            'csv', title)+ '.dat')


def check_for_child_params(params):
    check_gamma = params['gamma-instance'] == params['gamma-sub'] and params['gamma-sub'] == params['gamma-basic'] and params['gamma-basic'] == params['gamma-sup']
    check_k = params['k-instance'] == params['k-sub'] and params['k-sub'] == params['k-basic'] and params['k-basic'] == params['k-sup']
    check_p = params['p-instance'] == params['p-sub'] and params['p-sub'] == params['p-basic'] and params['p-basic'] == params['p-sup']
    check_decay = params['decay-instance'] == params['decay-sub'] and params['decay-sub'] == params['decay-basic'] and params['decay-basic'] == params['decay-sup']
    check_feature_weight = params['feature-weight-instance'] == params['feature-weight-sub'] and params['feature-weight-sub'] == params['feature-weight-basic'] and params['feature-weight-basic'] == params['feature-weight-sup']
    return check_gamma and check_k and check_p and check_decay and check_feature_weight

def spencer_condition(results, params):
    """Define the condition of having a reversal of the suspicious coincidence
    effect, as in the Spencer et al. paper."""
    normalisation = np.mean(results['one example']['subordinate matches']) + \
        np.mean(results['one example']['basic-level matches']) + \
        np.mean(results['one example']['superordinate matches'])
    one_ex = np.mean(results['one example']['basic-level matches']) / normalisation

    normalisation = np.mean(results['three subordinate examples']['subordinate matches']) + \
        np.mean(results['three subordinate examples']['basic-level matches']) + \
        np.mean(results['three subordinate examples']['superordinate matches'])
    three_sub = np.mean(results['three subordinate examples']['basic-level matches']) / normalisation

    one_ex_sub_basic_ratio =\
        np.mean(results['one example']['subordinate matches']) /\
        np.mean(results['one example']['basic-level matches'])

    return is_close(three_sub / one_ex, 1.3) and one_ex_sub_basic_ratio > 2

def xt_condition(results, params):
    """Define bounds on acceptable results."""

    # 1 ex.
    sub = np.mean(results['one example']['subordinate matches'])
    basic = np.mean(results['one example']['basic-level matches'])
    sup = np.mean(results['one example']['superordinate matches'])

    one_ex = is_close(basic/sub, params['one-ex-basic-sub-ratio']) and is_close(sup/sub, params['one-ex-sup-sub-ratio'])

    # 3 subord.
    sub = np.mean(results['three subordinate examples']['subordinate matches'])
    basic = np.mean(results['three subordinate examples']['basic-level matches'])
    sup = np.mean(results['three subordinate examples']['superordinate matches'])

    three_subord = is_close(basic/sub, params['three-subord-basic-sub-ratio']) and is_close(sup/sub, params['three-subord-sup-sub-ratio'])

    # 3 basic
    sub = np.mean(results['three basic-level examples']['subordinate matches'])
    basic = np.mean(results['three basic-level examples']['basic-level matches'])
    sup = np.mean(results['three basic-level examples']['superordinate matches'])

    three_basic = is_close(basic/sub, params['three-basic-basic-sub-ratio']) and is_close(sup/sub, params['three-basic-sup-sub-ratio'])

    # 3 super.
    sub = np.mean(results['three superordinate examples']['subordinate matches'])
    basic = np.mean(results['three superordinate examples']['basic-level matches'])
    sup = np.mean(results['three superordinate examples']['superordinate matches'])

    three_super = is_close(basic/sub, params['three-super-basic-sub-ratio']) and is_close(sup/sub, params['three-super-sup-sub-ratio'])

    return one_ex and three_subord and three_basic and three_super


def is_close(x, y, atol=0.2, rtol=0):
    return np.less_equal(abs(x-y), atol + rtol * y)


def write_suspicious_coincidence(results, savename):
    with open(savename, 'w') as f:
        f.write(
            str(
            (np.mean(results['one example']['basic-level matches']) /\
            np.mean(results['one example']['subordinate matches'])) /\
            (np.mean(results['three subordinate examples']['basic-level matches']) /\
            np.mean(results['three subordinate examples']['subordinate matches']))
        ))

def write_results_as_csv_file(results, savename):

    conditions = [
        'one example',
        'three subordinate examples',
        #'three basic-level examples',
        #'three superordinate examples'
    ]

    conditions = [
        'one example',
        'two subordinate examples',
        'two basic-level examples',
        'two superordinate examples',
        'three subordinate examples',
        'three basic-level examples',
        'three superordinate examples',
        'four subordinate examples',
        'four basic-level examples',
        'four superordinate examples',
    ]

    abbrev_condition_names = {
        'one example': '1 ex.',
        'two subordinate examples': '2 subord.',
        'two basic-level examples': '2 basic',
        'two superordinate examples': '2 super.',
        'three subordinate examples': '3 subord.',
        'three basic-level examples': '3 basic',
        'three superordinate examples': '3 super.',
        'four subordinate examples': '4 subord.',
        'four basic-level examples': '4 basic',
        'four superordinate examples': '4 super.',
    }

    with open(savename, 'w') as f:
        f.write("condition,sub. match,basic match,super. match\n")
        for condition in conditions:

            # TODO: choose appropriate normalisation
            normalisation = \
                np.mean(results[condition]['subordinate matches'])
            #    np.mean(results[condition]['subordinate matches']) + \
            #    np.mean(results[condition]['basic-level matches']) + \
            #    np.mean(results[condition]['superordinate matches'])

            f.write(abbrev_condition_names[condition])
            f.write(',')
            f.write(str(np.mean(results[condition]['subordinate matches'])/normalisation))
            f.write(',')
            f.write(str(np.mean(results[condition]['basic-level matches'])/normalisation))
            f.write(',')
            f.write(str(np.mean(results[condition]['superordinate matches'])/normalisation))
            f.write("\n")


def script(config_file, num_cores, **kwargs):

    # Parse the configuration file
    config_parser = ConfigParser()
    if not config_parser.read(config_file):
        raise SystemExit('Config file %s not found.' % config_file)

    # Generate the experimental conditions (by Cartesian product)
    paramlist = []
    for exp in config_parser.sections():
        params = items_to_params(config_parser.items(exp))
        params['name'] = exp
        paramlist.append(params)

    # Randomise the order of experiment conditions
    np.random.shuffle(paramlist)

    exp_list = generate_conditions(paramlist)

    # Run the experiment(s), using the specified number of cores
    if num_cores == 1:
        for e in exp_list:
            run_trial(e)

    else:
        pool = Pool(processes=num_cores)
        pool.map(run_trial, exp_list)
        pool.close()


def parse_args(args):
    parser = ArgumentParser()

    parser.add_argument('--logging', type=str, default='INFO',
                        metavar='logging', choices=['DEBUG', 'INFO', 'WARNING',
                                                    'ERROR', 'CRITICAL'],
                        help='Logging level')

    parser.add_argument('--config_file', '-c', metavar='config_file', type=str,
                        default='exp.cfg', help='The experiment config file')

    parser.add_argument('--num_cores', '-n', metavar='num__cores',
                        type=int, default=1,
                        help='Number of processes used; default is 1')

    parser.add_argument('--results_path', '-r', metavar='results_path',
                        type=str,
                        default=os.path.dirname(os.path.realpath(__file__)),
                        help='The path to which to write the results')

    return parser.parse_args(args)


def main(args=sys.argv[1:]):
    args = parse_args(args)
    logging.basicConfig(level=args.logging)
    script(**vars(args))


if __name__ == '__main__':
    sys.exit(main())
