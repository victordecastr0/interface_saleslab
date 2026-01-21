import streamlit as st


def build_availability_analysis(lead):
    availability_analysis = lead['vtal_availability']

    if availability_analysis is None:
        st.warning('A viabilidade ainda não foi consultada neste endereço...')
        return


    availability_analysis = availability_analysis['resource']

    st.caption('Viabilidade no Endereço')

    if availability_analysis['availabilityCode'] == 2:
        st.write(f":red[**{availability_analysis['availabilityDescription']}**]")

        if lead['hzn_address_info_result'] != 'reprovado':
            st.error(f"Cliente **reprovado** na consulta de viabilidade - {fmt_date(date.today())}")
            update_audit_step_features(lead['lead_id'], 'reprovado', 'address_info')
        else:
            st.error(f"Cliente **reprovado** na consulta de viabilidade - {fmt_date(lead['hzn_address_info_dt'])}")
    else:
        st.write(f":green[**{availability_analysis['availabilityDescription']}**]")
        st.success("Cliente **aprovado** na consulta de viabilidade!")

    return


def build_address_analysis(lead):
    address_data = lead['vtal_address']

    if address_data is None:
        st.warning('O endereço deste lead ainda não foi registrado...')
        return


    address_data = address_data['address']

    if len(address_data.keys()) == 2:
        address_data['neighborhood'] = '—'
        address_data['streetType'] = '—'
        address_data['streetName'] = '—'
        address_data['city'] = '—'
        address_data['state'] = '—'

    with st.container(border=True):
        st.write('Endereço Cadastrado')

        address_data_columns_top = st.columns(3)

        with address_data_columns_top[0]:
            st.caption('Bairro')
            st.write(address_data['neighborhood'])

        with address_data_columns_top[1]:
            st.caption('Rua')
            st.write(f'{address_data['streetType']} {address_data['streetName']}')

        with address_data_columns_top[2]:
            st.caption('Número')

            number = '—' if address_data['number'] is None else str(address_data['number'])
            st.write(number)

        address_data_columns_bottom = st.columns(3)

        with address_data_columns_bottom[0]:
            st.caption('Complemento')

            if lead['vtal_address_complements'] is not None:

                complement = [f'{compl['description']} {compl['value']}' for compl in lead['vtal_address_complements']['complement']['complements']]
                complement = ", ".join(complement)
            else:
                complement = '—'

            st.write(complement)

        with address_data_columns_bottom[1]:
            st.caption('CEP')
            st.write(fmt_zipcode(address_data['zipCode']))

        with address_data_columns_bottom[2]:
            st.caption('Cidade')
            st.write(f'{address_data['city']} - {address_data['state']}')

    st.caption('Link do comprovante de endereço enviado')
    doc_url = lead['doc_link'] if not pd.isna(lead['doc_link']) else '—'
    st.write(doc_url)

    if lead['all_addresses'] is not None:
        with st.expander('_Últimos endereços registrados - Serasa_', expanded=True ):
            st.table(
                build_tabela_enderecos(lead['all_addresses']),
                border="horizontal"
            )

    if 'vtal_availability' not in address_data:
        st.warning('Endereço ainda não foi corretamente cadastrado...')

    elif lead['vtal_availability']['resource']['availabilityCode'] == 2:
        st.error(f"Cliente **reprovado** na consulta de viabilidade - {fmt_date(lead['hzn_address_info_dt'])}")

    else:
        create_decision_structure('Resultado Análise do Endereço', 'address_info', lead)

    return



def buiild_street_view_analysis(lead):
    coords = lead['vtal_address']

    if coords is None or ('geolocation' not in coords['address']):
        st.warning('O endereço deste lead ainda não foi registrado...')
        return

    st.caption('Link Google Maps')
    coords = coords['address']['geolocation']
    
    if coords is None:
        st.write(':red[**O lead não possui coordenadas geográficas para visualização...**]')
        return

    coords = f"{coords['latitude']},+{coords['longitude']}"
    
    st.write(f'https://www.google.com.br/maps?q=&layer=c&cbll={coords}&cbp=11,150,0,0,0')

    create_decision_structure('Resultado Análise Google Street View', 'street_view', lead)
    return 