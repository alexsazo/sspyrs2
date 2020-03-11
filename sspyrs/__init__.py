import bs4

class report(object):
    """Create a report object with baseline attributes
    """

    # add option to export to different formats

    def __init__(self, link, username, password, parameters=None):
        """Iniates a report object
        Parameters
        ----------
        link : str
            The raw link of the report to use.
        username : str
            The username to access the report
        password : str
            The password to access the report
        parameters : dict 
            A dictionary of parameters to pass to the report
        """
        self.link = link
        self.username = username
        self.password = password
        self.reportname = ''
        self.session = None
        self.post_data = {}
        
        if parameters is not None and type(parameters) != dict:
            raise ValueError('Invalid parameters')
        else:
            self.parameters = parameters

        def exportlink(link, username, password, parameters):
            """Generate a link to a report session
            Returns
            -------
            str
                Link with valid session to get the export information.
            """
            import re
            import requests
            from requests_ntlm import HttpNtlmAuth
            from xmltodict import parse


            def addparams(link, params):
                linkstring = link
                if params is not None:
                    for i in params.keys():
                        keylabel = i
                        keyvalue = params[i]
                        linkstring += '&' + str(keylabel) + '=' + str(keyvalue)

                return linkstring

            self.link_param = addparams(link, parameters)

            self.linkbase = self.link_param[:re.search('/report', self.link_param.lower()).start(0) + 1]

            self.session = requests.session()
            self.session.auth = HttpNtlmAuth(username,
                                        password,
                                        self.session)

            if self.parameters:
                pg = self.post_to_get_page()
            else:
                pg = self.session.get(self.link_param)
            pg_text = pg.text
            pg_text_split = pg_text.split('\n')

            outputs = [s.replace('\t', '') for s in pg_text_split if 'exportReport(' in s]
            outputs = [parse(s)['a']['#text'] for s in outputs]

            # Preferimos la descarga por PDF SIEMPRE
            if 'Archivo XML con datos de informe' in outputs and 'PDF' not in outputs:
                relpage = [s for s in pg_text_split if 'ExportUrlBase' in s][0]
                relpage = relpage.replace('\\u0026', '&')
                linkstart = re.search('ExportUrlBase', relpage).start(0) + 17
                linkend = re.search('FixedTableId', relpage).start(0) - 3
                exportlink = relpage[linkstart:linkend]
                newlink = self.linkbase + exportlink + 'XML'
                return newlink, outputs
            
            elif 'PDF' in outputs:
                relpage = [s for s in pg_text_split if 'ExportUrlBase' in s][0]
                relpage = relpage.replace('\\u0026', '&')
                linkstart = re.search('ExportUrlBase', relpage).start(0) + 17
                linkend = re.search('FixedTableId', relpage).start(0) - 3
                exportlink = relpage[linkstart:linkend]
                newlink = self.linkbase + exportlink + 'PDF'
                return newlink, outputs                
            
            elif 'Excel' in outputs:
                wrnstr = 'No XML export allowed from report server. Use direct excel download function.'

            elif 'CSV (delimitado por comas)' in outputs:
                wrnstr = 'No XML/Excel export allowed from report server. Use direct csv download function.'
            
            else:
                wrnstr = 'Report Server does not allow usable data export methods. Update server settings/version to enable XML, Excel, or CSV export.'

            # warnings.warn(wrnstr, RuntimeWarning)
            print(wrnstr)
            return None, outputs

        self.exportlink, self.available_exports = exportlink(self.link,
                                                             self.username,
                                                             self.password,
                                                             self.parameters)



    def rawdata(self):
        """Retrieve raw report XML data as a dictionary
        Useful in the case of special reports which may contain graphs, 
        unstructured information, or other inconsistencies. 
        Returns
        -------
        dict
            Dictionary of report data
        """
        import requests
        import xmltodict
        from re import search
        from requests_ntlm import HttpNtlmAuth


        if self.exportlink is None:
            raise ValueError('No valid export link available.')

        self.session = requests.session()
        self.session.auth = HttpNtlmAuth(self.username,
                                    self.password,
                                    self.session)

        pg = self.session.get(self.exportlink)
        pg_txt = pg.text[search('<', pg.text).start():]
        pg_xml = xmltodict.parse(pg_txt)
        self.reportname = pg_xml['Report']['@Name']
        self.tables = [x for x in list(pg_xml['Report'].keys()) if
                       '@' not in x and pg_xml['Report'][x] is not None]
        return pg_xml

    def tabledata(self, guessdatatypes=True):
        """Retrieve only table data from XML
        Returns
        -------
        dict
            Dictionary of pandas DataFrame objects
        """
        from pandas import DataFrame, to_numeric, to_datetime
        from re import search
        rawdata = self.rawdata()
        xmltables = [x for x in list(rawdata['Report'].keys()) if '@' not in x]
        datadict = {}
        for t in xmltables:
            t_group = rawdata['Report'][t]
            if t_group is not None:
                t_details_col = t_group[list(t_group.keys())[0]]
                t_details = t_details_col[list(t_details_col.keys())[0]]
                if type(t_details) != list:
                    t_details = [t_details]
                df = DataFrame.from_records(t_details, columns=t_details[0].keys())
                df.columns = [x.replace('@', '') for x in df.columns]
                columnends = [x[-1:] for x in df.columns]
                if all([x == columnends[0] for x in columnends]):
                    if search('[0-9]', columnends[0]).start() >= 0:
                        df.columns = [x[:-1] for x in df.columns]

                def guesstype(ser, sample=50):
                    sersam = ser.sample(min(sample, len(ser)))
                    if all([x[5] == '-' and x[10] == 'T' for x in sersam]):
                        return 'date'
                    else:
                        return 1

                #todo add float parser
                datadict[t] = df
            else:
                import warnings
                warnings.warn(
                    'Table ' + t + ' detected with no data, skipping.')
        return datadict

    def download(self, exportformat='CSV', filename=None, path=None):
        """
        Parameters
        ----------
        exportformat : str
            The format to export the data. Allows excel, json, or csv. Not
            case sensitive. For csv and json, files are created with the
            format <reportname>__<tableobjname>.<ext>. For excel files, 
            the workbook is titled <reportname>.xlsx, and the sheets within 
            are titled by table object name. 
        Returns
        -------
        list
            The list of files/sheets that were successfully written
        """
        from os import path
        from pandas import DataFrame
        exportformat = exportformat.upper()
        allowedformats = ['CSV', 'JSON', 'EXCEL', 'PDF']

        if exportformat not in allowedformats:
            raise ValueError('Format not in allowed types.')

        def filever(fname):
            if not path.exists(fname):
                return fname
            else:
                filename, file_extension = path.splitext(fname)
                i = 0
                while i < 5:
                    tmpname = filename + '_' + str(i) + file_extension
                    if not path.exists(tmpname):
                        return tmpname
                    else:
                        i += 1

        if filename == None:
            basename = filever(self.reportname)
        else:
            basename = filename

        files = []

        if exportformat == 'PDF':
            if self.parameters:
                r = self.session.post(self.exportlink, self.post_data)
            else:
                r = self.session.post(self.exportlink)
            if r.status_code == 200:
                with open(basename, 'wb') as out:
                    for bits in r.iter_content():
                        out.write(bits)
            files.append(basename)
            
        elif exportformat != 'EXCEL':
            data = self.tabledata()
            for dskey in self.tables:
                dataset = data[dskey]
                if exportformat == 'CSV':
                    exportdest = filever(basename + '__' + dskey + '.csv')
                    dataset.to_csv(exportdest)
                    files += [exportdest]
                elif exportformat == 'JSON':
                    exportdest = filever(basename + '__' + dskey + '.json')
                    dataset.to_json(exportdest)
                    files += [exportdest]
                else:
                    pass        
        else:
            data = self.tabledata()
            from pandas import ExcelWriter, DataFrame
            writer = ExcelWriter(filever(basename + '.xlsx'))
            for dskey in self.tables:
                dataset = data[dskey]
                dataset.to_excel(writer, dskey, index=False)
                files += [dskey]
            writer.save()

        return files


    def directdown(self, type='EXCELOPENXML'):
        return type

    def get_data_to_post(self):
        r = self.session.get(self.link)
        soup = bs4.BeautifulSoup(r.content, "html.parser")
        inputs = soup.find_all("input")
        key_by_name = {}
        name_by_key = {}
        post_data = {}

        for i in inputs:            
            post_data[i.attrs['name']] = i.attrs.get('value')
            
            if i.attrs['name'].endswith("txtValue"):
                # En caso de que sea un txt input
                span = i.findPrevious('span')
                key = span.text
                key_by_name[i.attrs["name"]] = key
                name_by_key[key] = i.attrs["name"]
                                
        for k,v in self.parameters.items():
            post_data[name_by_key[k]] = v

        self.post_data = post_data
        return post_data

    def post_to_get_page(self, data=None):
        if data:
            return self.session.post(self.link, data)        
        return self.session.post(self.link, self.get_data_to_post())
