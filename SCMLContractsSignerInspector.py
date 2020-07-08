from prettytable import PrettyTable
import pulp
from SCMLContractsSigner import SCMLContractsSigner


class SCMLContractsSignerInspector:

    @staticmethod
    def signer_inspector(signer_output, title='Optimal Solver'):
        """
        This function takes the output of a signer and outputs useful info. Used for debugging purposes.
        :param signer_output: could be the optimal signer or the greedy signer
        :param title: a human readable title
        """
        agreements_table = PrettyTable()
        agreements_table.field_names = ['t', 'q', 'p', 'is_buy', 'partners', 'trust', 'signed?']
        for i, a in enumerate(signer_output['agreements']):
            agreements_table.add_row([a['agreement']['time'],
                                      a['agreement']['quantity'],
                                      f"{a['agreement']['unit_price'] : .4f}",
                                      a['annotation']['is_buy'],
                                      a['partners'],
                                      f"{SCMLContractsSigner.find_partner_trust(agent_id=signer_output['agent_id'], agreement=a, trust_probabilities=signer_output['trust_probabilities']) : .4f}",
                                      'yes' if signer_output['list_of_signatures'][i] is not None else 'No'])
        print(f"\n--- Agreements given to {title} ---")
        print(agreements_table)

        # Pretty table print of the buy and sell plan.
        horizon, buy_plan, sell_plan = SCMLContractsSigner.get_plan_as_lists(signer_output)
        signature_plan_table = PrettyTable()
        signature_plan_table.field_names = ['t'] + [str(t) for t in range(0, horizon)] + ['total']
        signature_plan_table.add_row(['buy'] + buy_plan + [sum(buy_plan)])
        signature_plan_table.add_row(['sel'] + sell_plan + [sum(sell_plan)])
        print('\n--- Signatures Plan ---')
        print(signature_plan_table)

    @staticmethod
    def solver_statistics(signer_output):
        """
        Prints statistics of the optimal solver.
        :param signer_output: the output of the optimal solver.
        :return: None
        """
        # Print solve time info.
        statistics_table = PrettyTable()
        statistics_table.field_names = ['Statistic', 'Value']

        time_to_generate_ilp = None
        if signer_output['time_to_generate_ilp'] is not None:
            time_to_generate_ilp = f"{signer_output['time_to_generate_ilp'] : .4f}"
        statistics_table.add_row(['time to generate the ILP', f'{time_to_generate_ilp} sec.'])

        time_to_solve_ilp = None
        if signer_output['time_to_solve_ilp'] is not None:
            time_to_solve_ilp = f"{signer_output['time_to_solve_ilp'] : .4f}"
        statistics_table.add_row(['time to solve the ILP', f"{time_to_solve_ilp} sec."])

        total_time = None
        if signer_output['time_to_generate_ilp'] is not None and signer_output['time_to_solve_ilp'] is not None:
            total_time = f"{signer_output['time_to_generate_ilp'] + signer_output['time_to_solve_ilp'] : .4f}"
        statistics_table.add_row(['total solver time', f'{total_time} sec.'])

        status = None
        if signer_output['model'] is not None:
            status = pulp.LpStatus[signer_output['model'].status]
        statistics_table.add_row(['solver status', f'{status}'])

        objective = None
        if signer_output['model'] is not None:
            objective_value = None
            if pulp.value(signer_output['model'].objective) is not None:
                objective_value = pulp.value(signer_output['model'].objective)
            objective = f"{objective_value}"
        statistics_table.add_row(['optimal profit', f'{objective}'])

        statistics_table.align['Statistic'] = 'r'
        print(statistics_table)
