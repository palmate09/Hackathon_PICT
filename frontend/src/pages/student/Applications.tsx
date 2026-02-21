import React from 'react';
import { useSearchParams } from 'react-router-dom';
import Opportunities from './Opportunities';

const StudentApplications: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  
  const tab = searchParams.get('tab') || 'applications';

  React.useEffect(() => {
    if (!searchParams.get('tab')) {
      setSearchParams({ tab: 'applications' });
    }
  }, [searchParams, setSearchParams]);

  return <Opportunities initialTab={tab} />;
};

export default StudentApplications;
