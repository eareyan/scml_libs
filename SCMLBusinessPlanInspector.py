from prettytable import PrettyTable


class SCMLBusinessPlanInspector:

    @staticmethod
    def inspect_business_plan(business_plan_output):
        ptable_plan = PrettyTable()
        ptable_plan.field_names = ['t'] + [str(t) for t in range(0, business_plan_output['horizon'])] + ['total']
        total_buy_qtty = sum([business_plan_output['buy_plan'][t] for t in range(0, business_plan_output['horizon'])])
        ptable_plan.add_row(['B-Q'] + [str(business_plan_output['buy_plan'][t]) for t in range(0, business_plan_output['horizon'])] + [str(total_buy_qtty)])
        total_sell_qtty = sum([business_plan_output['sell_plan'][t] for t in range(0, business_plan_output['horizon'])])
        ptable_plan.add_row(['S-Q'] + [str(business_plan_output['sell_plan'][t]) for t in range(0, business_plan_output['horizon'])] + [str(total_sell_qtty)])
        ptable_plan.add_row(['B-P'] + [str(round(business_plan_output['p_inn'][t], 2)) for t in range(0, business_plan_output['horizon'])] + ['--'])
        ptable_plan.add_row(['S-P'] + [str(round(business_plan_output['p_out'][t], 2)) for t in range(0, business_plan_output['horizon'])] + ['--'])
        total_exp_buy_qtty = sum([business_plan_output['inn'][t][business_plan_output['buy_plan'][t]] for t in range(0, business_plan_output['horizon'])])
        ptable_plan.add_row(['B-E'] + [str(round(business_plan_output['inn'][t][business_plan_output['buy_plan'][t]], 2)) for t in range(0, business_plan_output['horizon'])] + [str(round(total_exp_buy_qtty, 2))])
        total_exp_sell_qtty = sum([business_plan_output['out'][t][business_plan_output['sell_plan'][t]] for t in range(0, business_plan_output['horizon'])])
        ptable_plan.add_row(['S-E'] + [str(round(business_plan_output['out'][t][business_plan_output['sell_plan'][t]], 2)) for t in range(0, business_plan_output['horizon'])] + [str(round(total_exp_sell_qtty, 2))])

        print(ptable_plan)

        ptable_stats = PrettyTable()
        ptable_stats.field_names = ['statistic', 'value']
        ptable_stats.add_row(['horizon', business_plan_output['horizon']])
        ptable_stats.add_row(['q_max', business_plan_output['q_max']])
        ptable_stats.add_row(['total profit',
                              f"{sum([business_plan_output['out'][t][business_plan_output['sell_plan'][t]] * business_plan_output['p_out'][t] - business_plan_output['inn'][t][business_plan_output['buy_plan'][t]] * business_plan_output['p_inn'][t] for t in range(0, business_plan_output['horizon'])]) :.4f}"])
        ptable_stats.add_row(['time_to_generate_variables', f"{business_plan_output['time_to_generate_variables'] : .4f} sec"])
        ptable_stats.add_row(['time_to_generate_objective', f"{business_plan_output['time_to_generate_objective'] : .4f} sec"])
        ptable_stats.add_row(['time_to_generate_constraints', f"{business_plan_output['time_to_generate_constraints'] : .4f} sec"])
        ptable_stats.add_row(['time_to_solve', f"{business_plan_output['time_to_solve'] : .4f} sec"])
        ptable_stats.add_row(['time_to_read_plan', f"{business_plan_output['time_to_read_plan'] : .4f} sec"])
        ptable_stats.add_row(['optimistic', f"{business_plan_output['optimistic']}"])

        print(ptable_stats)
